"""Installer: official release archives, strict extraction into the new SSD root."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import tarfile
import httpx
from assistant.config import STATE
from assistant.storage import bound_root

root = bound_root(STATE / "storage.json")
assets = [
 ("wake_word","kws-models","sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2"),
 ("speech_to_text","asr-models","sherpa-onnx-whisper-tiny.en.tar.bz2")]
manifest=[]
for category,tag,name in assets:
    dest = "model_cache/"+name
    try: filename = root.runtime_path(dest)
    except FileNotFoundError:
        with root.parent(dest) as (parent,leaf):
            fd=os.open(leaf,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            with os.fdopen(fd,"wb") as f, httpx.stream("GET","https://github.com/k2-fsa/sherpa-onnx/releases/download/"+tag+"/"+name,follow_redirects=True,timeout=90) as r:
                r.raise_for_status()
                for block in r.iter_bytes(1024*1024): f.write(block)
        filename=root.runtime_path(dest)
    h=hashlib.sha256()
    with open(filename,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    with tarfile.open(filename,"r:bz2") as archive:
        for item in archive:
            p=PurePosixPath(item.name)
            if p.is_absolute() or ".." in p.parts or item.issym() or item.islnk() or not (item.isfile() or item.isdir()):
                raise ValueError("Unsafe release archive")
            relative="models/"+category+"/"+str(p)
            if item.isdir():root.mkdir(relative);continue
            root.mkdir(str(PurePosixPath(relative).parent))
            try:root.write_new(relative,archive.extractfile(item).read())
            except FileExistsError:raise RuntimeError("Refusing to overwrite an existing model file: "+relative)
    manifest.append({"asset":name,"sha256":h.hexdigest(),"source":"https://github.com/k2-fsa/sherpa-onnx/releases/tag/"+tag})
    print("Installed",name,flush=True)
(STATE/"speech-manifest.json").write_text(json.dumps(manifest,indent=2))
