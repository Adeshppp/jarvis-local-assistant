"""On-demand personal filesystem tools. No background indexing or privilege escalation.

Runtime access is operator configured. Installer/model storage still uses storage.Root.
Mutations bind canonical targets and content versions to a reviewable approval.
"""
from __future__ import annotations
import base64
from contextlib import contextmanager
import difflib
import fnmatch
import hashlib
import io
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import uuid
from .config import STATE
from .storage import BoundaryError, Root

MAX_BYTES=25*1024*1024

class PersonalFiles:
    def __init__(self,config,state=None):
        self.config=config
        self.state=Path(state or STATE)

    def path(self,value,*,leaf=True):
        if self.config.get("filesystem",{}).get("mode")!="full":
            raise BoundaryError("Personal filesystem access is not enabled")
        if not isinstance(value,str) or not value or "\0" in value:
            raise ValueError("A file path is required")
        path=Path(os.path.expanduser(value))
        if not path.is_absolute():
            raise ValueError("Use an absolute path or ~/ path; search_files can find unknown paths")
        if leaf:return path.resolve(strict=False)
        return path.parent.resolve(strict=True)/path.name

    @staticmethod
    def version(path):
        try:s=path.lstat()
        except FileNotFoundError:return None
        result={"device":s.st_dev,"inode":s.st_ino,"size":s.st_size,"modified_ns":s.st_mtime_ns,
                "mode":stat.S_IMODE(s.st_mode),"kind":"directory" if stat.S_ISDIR(s.st_mode) else "link" if stat.S_ISLNK(s.st_mode) else "file"}
        if stat.S_ISREG(s.st_mode):
            if s.st_size>MAX_BYTES:
                result["sha256"]=None
            else:result["sha256"]=hashlib.sha256(PersonalFiles.bytes(path)).hexdigest()
        return result

    @staticmethod
    def bytes(path,limit=MAX_BYTES):
        # Full runtime access has no directory allowlist. Open the canonical file
        # directly, without requesting enumeration rights on all of its parents.
        # Final-component no-follow and regular-file checks still apply.
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as file:
            info=os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode):raise ValueError("Select a regular file")
            if info.st_size>limit:raise ValueError("File exceeds the extraction limit; use metadata, open it, or select a smaller file")
            return file.read(limit+1)

    @staticmethod
    def sensitive(path):
        parts=set(path.parts)
        return bool(parts & {".ssh",".gnupg","Keychains"} or path.name in {".env","credentials","bootstrap-token","server-key.pem","ca-key.pem"}
                    or ("device-connections" in parts and path.suffix==".json"))

    def info(self,value):
        path=self.path(value);s=path.stat()
        return {"path":str(path),"name":path.name,"size":s.st_size,"directory":stat.S_ISDIR(s.st_mode),
                "modified":s.st_mtime,"readable":os.access(path,os.R_OK),"writable":os.access(path,os.W_OK)}

    def listing(self,value,offset=0,limit=100):
        path=self.path(value)
        result=[];skipped=0;more=False
        with os.scandir(path) as entries:
            for entry in entries:
                if skipped<offset:skipped+=1;continue
                if len(result)>=limit:more=True;break
                try:
                    info=entry.stat(follow_symlinks=False)
                    result.append({"name":entry.name,"path":str(path/entry.name),"directory":stat.S_ISDIR(info.st_mode),"symlink":entry.is_symlink(),"size":info.st_size})
                except OSError:continue
        return {"path":str(path),"offset":offset,"items":result,"next_offset":offset+len(result) if more else None}

    def search(self,query,scope="computer",path=None,limit=30,content=False,seconds=8,use_index=True):
        if path:roots=[self.path(path)]
        elif scope=="home":roots=[Path.home()]
        elif scope in ("ssd","volumes"):roots=[Path(self.config.get("filesystem",{}).get("ssd_mount","/Volumes/Sandisk"))] if scope=="ssd" else [Path("/Volumes")]
        else:roots=[Path.home(),Path("/Volumes"),Path("/")]
        deadline=time.monotonic()+seconds
        results=[];seen=set();visited=set();denied=0;scanned=0;partial=False
        def add(candidate,excerpt=None):
            if str(candidate) in seen:return
            seen.add(str(candidate));row={"path":str(candidate),"name":candidate.name}
            if excerpt is not None:row["excerpt"]=excerpt
            results.append(row)
        # Spotlight is queried only in response to this explicit runtime request.
        # Test callers can disable it and limit the search to their own fixtures.
        if use_index and not content:
            safe=query.replace("\\","\\\\").replace('"','\\"')
            predicate='kMDItemFSName == "*'+safe+'*"cd'
            for root in roots:
                try:
                    p=subprocess.run(["/usr/bin/mdfind","-0","-onlyin",str(root),predicate],capture_output=True,timeout=min(2,max(.1,deadline-time.monotonic())))
                    for raw in p.stdout.split(b"\0"):
                        if raw:
                            candidate=Path(os.fsdecode(raw))
                            # Treat index output as data; verify it belongs to scope.
                            if candidate.is_relative_to(root) and candidate.exists():add(candidate)
                            if len(results)>=limit:return {"matches":results,"partial":True,"method":"Spotlight","searched_roots":[str(r) for r in roots]}
                except (OSError,subprocess.TimeoutExpired):pass
        needle=query.casefold()
        for root in roots:
            queue=[root]
            while queue:
                if time.monotonic()>deadline or len(results)>=limit:partial=True;break
                directory=queue.pop()
                try:
                    s=directory.stat();key=(s.st_dev,s.st_ino)
                    if key in visited:continue
                    visited.add(key)
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            scanned+=1
                            if scanned%64==0 and time.monotonic()>deadline:partial=True;break
                            candidate=directory/entry.name
                            if needle in entry.name.casefold() or fnmatch.fnmatch(entry.name.casefold(),needle):add(candidate)
                            if content and entry.is_file(follow_symlinks=False) and not self.sensitive(candidate):
                                try:
                                    if entry.stat(follow_symlinks=False).st_size<=256000:
                                        text=self.bytes(candidate,256000).decode("utf-8")
                                        at=text.casefold().find(needle)
                                        if at>=0:add(candidate,text[max(0,at-80):at+240])
                                except (OSError,UnicodeError,ValueError):pass
                            if entry.is_dir(follow_symlinks=False):queue.append(candidate)
                            if len(results)>=limit:partial=True;break
                except OSError:denied+=1
                if partial:break
            if partial:break
        return {"matches":results,"partial":partial,"scanned_entries":scanned,"inaccessible_directories":denied,
                "searched_roots":[str(r) for r in roots],"note":"On-demand search only. Refine the path/query if partial. macOS permissions are respected."}

    def read(self,value,offset=0,limit=6000):
        path=self.path(value);raw=self.bytes(path);suffix=path.suffix.lower()
        if suffix==".pdf":
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:raise ValueError("The PDF is encrypted; unlock it in its application first")
            text="\n".join((page.extract_text() or "") for page in list(reader.pages)[:100])
            kind="PDF text"
        elif suffix==".docx":
            self.check_zip(raw)
            from docx import Document
            document=Document(io.BytesIO(raw))
            text="\n".join([p.text for p in document.paragraphs]+[" | ".join(c.text for c in row.cells) for t in document.tables for row in t.rows])
            kind="Word text"
        elif suffix in (".xlsx",".xlsm"):
            self.check_zip(raw)
            from openpyxl import load_workbook
            workbook=load_workbook(io.BytesIO(raw),read_only=True,data_only=False)
            lines=[]
            try:
                for sheet in workbook:
                    lines.append("Sheet: "+sheet.title)
                    for row in sheet.iter_rows():
                        lines.append(" | ".join(f"{cell.coordinate}={cell.value}" for cell in row if cell.value is not None))
                        if sum(map(len,lines))>200000:break
            finally:workbook.close()
            text="\n".join(lines);kind="Spreadsheet cells"
        elif suffix==".rtf":
            p=subprocess.run(["/usr/bin/textutil","-convert","txt","-stdin","-stdout","-format","rtf"],input=raw,capture_output=True,check=True,timeout=15)
            text=p.stdout.decode("utf-8");kind="Rich text"
        else:
            try:text=raw.decode("utf-8-sig")
            except UnicodeError:
                return {"path":str(path),"format":"binary","size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"note":"Use open_file for this format; binary content is not interpreted as text."}
            if "\0" in text:return {"path":str(path),"format":"binary","size":len(raw),"note":"Use open_file for this format."}
            kind="UTF-8 text"
        return {"path":str(path),"format":kind,"size":len(raw),"offset":offset,"read_authorized":True,"content_available":True,"untrusted_data":text[offset:offset+limit],
                "total_characters":len(text),"next_offset":offset+limit if len(text)>offset+limit else None}

    @staticmethod
    def check_zip(raw):
        import zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist())>5000 or sum(i.file_size for i in archive.infolist())>100*1024*1024:
                raise ValueError("Document extraction limit exceeded")

    def transformed(self,operation,a):
        path=self.path(a["path"])
        original=self.bytes(path) if path.exists() else None
        if operation=="write_file":
            if original is not None and not a.get("overwrite"):
                raise FileExistsError("File already exists; set overwrite only when the user explicitly requests replacement")
            data=base64.b64decode(a["content"],validate=True) if a.get("encoding")=="base64" else a["content"].encode("utf-8")
            return original,data,{"encoding":a.get("encoding","utf-8")}
        if original is None:raise FileNotFoundError(path)
        suffix=path.suffix.lower()
        if suffix==".docx":
            self.check_zip(original)
            from docx import Document
            document=Document(io.BytesIO(original))
            paragraphs=list(document.paragraphs)+[p for table in document.tables for row in table.rows for cell in row.cells for p in cell.paragraphs]
            old=a["old_text"];new=a["new_text"]
            if not old:raise ValueError("old_text is required for Word edits")
            count=sum(p.text.count(old) for p in paragraphs)
            if not count or (count!=1 and not a.get("replace_all")):raise ValueError("The text must match exactly once; use a more specific match or explicitly replace all")
            if sum(''.join(run.text for run in p.runs).count(old) for p in paragraphs)!=count:
                raise ValueError('This match includes a hyperlink or unsupported Word field; choose plain paragraph text')
            for paragraph in paragraphs:
                matches=list(re.finditer(re.escape(old),''.join(run.text for run in paragraph.runs)))
                for match in reversed(matches):
                    start=match.start();end=match.end();position=0;inserted=False
                    for run in paragraph.runs:
                        value=run.text;stop=position+len(value)
                        if stop>start and position<end:
                            before=value[:max(0,start-position)];after=value[max(0,end-position):] if end<stop else ""
                            run.text=before+(new if not inserted else "")+after;inserted=True
                        position=stop
            output=io.BytesIO();document.save(output)
            return original,self.stable_zip(output.getvalue()),{"format":"Word","matches":count,"old_text":old,"new_text":new}
        if suffix==".xlsx":
            self.check_zip(original)
            from openpyxl import load_workbook
            workbook=load_workbook(io.BytesIO(original))
            if not a.get("cell"):raise ValueError("Spreadsheet edits require cell and optionally sheet")
            sheet=workbook[a["sheet"]] if a.get("sheet") else workbook.active
            cell=sheet[a["cell"]]
            before=cell.value
            try:value=json.loads(a["new_text"])
            except (ValueError,TypeError):value=a["new_text"]
            if isinstance(value,(dict,list)):raise ValueError("A cell value must be text, a number, a boolean, or null")
            cell.value=value;output=io.BytesIO();workbook.save(output);workbook.close()
            return original,self.stable_zip(output.getvalue()),{"format":"Excel","sheet":sheet.title,"cell":a["cell"],"before":str(before),"after":str(value)}
        if suffix in (".pdf",".xlsm",".xls",".pptx",".pages",".numbers"):
            raise ValueError("This format can be read/opened but requires its document application for editing; it will not be overwritten as plain text")
        text=original.decode("utf-8")
        if "\0" in text:raise ValueError("Binary files need an explicit base64 write; text replacement is disabled")
        old=a["old_text"]
        if not old:raise ValueError("old_text is required")
        count=text.count(old)
        if count==0:raise ValueError("old_text was not found exactly")
        if count>1 and not a.get("replace_all"):raise ValueError("Multiple matches; choose more specific text or explicitly replace all")
        changed=text.replace(old,a["new_text"],-1 if a.get("replace_all") else 1)
        return original,changed.encode("utf-8"),{"matches":count if a.get("replace_all") else 1}

    @staticmethod
    def stable_zip(data):
        import zipfile
        output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(output,'w') as target:
            for entry in source.infolist():
                entry.date_time=(1980,1,1,0,0,0)
                target.writestr(entry,source.read(entry.filename))
        return output.getvalue()

    @staticmethod
    def destructive_guard(path):
        protected={Path("/"),Path("/Users"),Path("/System"),Path("/Library"),Path("/Applications"),Path("/Volumes"),Path.home()}
        if path in protected or path.parent==Path("/Volumes"):
            raise BoundaryError("Select an individual file or folder; whole computer, home and volume removal is not supported")

    def prepare(self,operation,a):
        path=self.path(a["path"],leaf=operation not in ("move_file","delete_file"))
        if operation in ("move_file","delete_file"):self.destructive_guard(path)
        guard={"path":str(path),"version":self.version(path),"parent_version":self.directory_version(path.parent)}
        preview={"operation":operation,"path":str(path)}
        if operation in ("write_file","edit_file"):
            before,after,detail=self.transformed(operation,{**a,"path":str(path)})
            guard["new_sha256"]=hashlib.sha256(after).hexdigest()
            preview.update(detail);preview.update(bytes_before=len(before) if before is not None else 0,bytes_after=len(after))
            try:
                preview["diff"]="".join(difflib.unified_diff((before or b"").decode().splitlines(True),after.decode().splitlines(True),fromfile=str(path),tofile=str(path)))[:6000]
            except UnicodeError:pass
        elif operation=="move_file":
            if guard["version"] is None:raise FileNotFoundError(path)
            destination=self.path(a["destination"],leaf=False)
            if destination.exists() or destination.is_symlink():raise FileExistsError("Destination exists; choose a new name")
            if not destination.parent.is_dir():raise ValueError("Destination folder does not exist")
            if destination.is_relative_to(path):raise ValueError("Cannot move a folder inside itself")
            guard["destination"]=str(destination);guard["destination_parent"]=self.directory_version(destination.parent)
            preview["destination"]=str(destination)
        elif operation=="delete_file":
            if guard["version"] is None:raise FileNotFoundError(path)
            preview["method"]="PERMANENT DELETE" if a.get("permanent") else "Move to Trash (recoverable)"
            if a.get("permanent") and guard["version"]["kind"]=="directory":
                raise ValueError("Use Trash for folders; recursive permanent directory deletion is not enabled")
        elif operation=="read_file":preview["reason"]="Credential/private-key file read requires explicit approval"
        return {"guard":guard,"preview":preview}

    @staticmethod
    def directory_version(path):
        s=path.stat();return [s.st_dev,s.st_ino]

    def verify(self,binding):
        guard=binding["guard"];path=Path(guard["path"])
        if self.directory_version(path.parent)!=guard["parent_version"] or self.version(path)!=guard["version"]:
            raise BoundaryError("The target changed since the preview; request a fresh approval")
        if "destination" in guard:
            destination=Path(guard["destination"])
            if self.directory_version(destination.parent)!=guard["destination_parent"] or destination.exists() or destination.is_symlink():
                raise BoundaryError("The destination changed; request a fresh approval")
        return path

    def helper(self,operation,**values):
        executable=Path(self.config.get("filesystem",{}).get("helper",str(self.state.parent/"vendor/file-actions")))
        p=subprocess.run([str(executable)],input=json.dumps({"action":operation,**values}),capture_output=True,text=True,timeout=30)
        if p.returncode:raise RuntimeError(p.stderr.strip()[:400] or "The macOS file operation failed")
        return json.loads(p.stdout)

    def commit(self,operation,a,binding):
        path=self.verify(binding);guard=binding["guard"]
        if operation in ("write_file","edit_file"):
            before,after,detail=self.transformed(operation,{**a,"path":str(path)})
            if hashlib.sha256(after).hexdigest()!=guard["new_sha256"]:raise BoundaryError("The proposed content changed; request another preview")
            undo=self.state/"file-undo"/uuid.uuid4().hex
            undo.mkdir(parents=True,mode=0o700)
            if before is not None:
                (undo/"original").write_bytes(before);(undo/"original").chmod(0o600)
            (undo/"record.json").write_text(json.dumps({"path":str(path),"version":guard["version"],"new_sha256":guard["new_sha256"]}))
            # Stage in the destination directory and use macOS's atomic replacement
            # to retain the original file's metadata/ACL. New files never overwrite.
            fd,temp=tempfile.mkstemp(prefix=".jarvis-edit-",dir=path.parent)
            try:
                with os.fdopen(fd,"wb") as file:file.write(after);file.flush();os.fsync(file.fileno())
                self.verify(binding)
                if before is not None:
                    self.helper("replace",path=str(path),replacement=temp)
                else:self.helper("move",path=temp,destination=str(path))
            finally:
                try:os.unlink(temp)
                except FileNotFoundError:pass
            return {"changed":str(path),"bytes":len(after),"undo_record":str(undo/"record.json")}
        if operation=="move_file":
            result=self.helper("move",path=str(path),destination=guard["destination"])
            return {"moved":str(path),"destination":guard["destination"],**result}
        if operation=="delete_file":
            if a.get("permanent"):
                os.unlink(path)
                return {"permanently_deleted":str(path)}
            return self.helper("trash",path=str(path))
        if operation=="read_file":return self.read(str(path),a.get("offset",0),a.get("limit",6000))
        raise ValueError("Unknown filesystem mutation")
