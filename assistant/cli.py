from __future__ import annotations
import argparse
import datetime
import json
import os
from pathlib import Path
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from .config import BASE, STATE, load, save
from .db import Database
from .service import profile, runtime_profile
from .setup import initialize, private
from .storage import bound_root, BoundaryError

LABEL="local.personal-ai.server"
DOMAIN="gui/"+str(os.getuid())

def local_token():
    bootstrap=STATE/"bootstrap-token"
    if bootstrap.exists():return bootstrap.read_text().strip()
    p=subprocess.run(["/usr/bin/security","find-generic-password","-s","local.personal-ai.device","-a","macbook-air","-w"],capture_output=True,text=True)
    if p.returncode:raise RuntimeError("Device token unavailable; open the desktop client once or provision a replacement locally")
    return p.stdout.strip()

def api(path,body=None):
    import httpx
    import ssl
    context=ssl.create_default_context(cafile=str(STATE/"tls/ca.pem"))
    with httpx.Client(verify=context,timeout=120,trust_env=False) as c:
        kwargs={"headers":{"Authorization":"Bearer "+local_token()}}
        if body is not None:kwargs["json"]=body
        r=c.request("POST" if body is not None else "GET","https://localhost:8765/api/"+path,**kwargs)
        r.raise_for_status();return r.json()

def install():
    initialize()
    sb=STATE/"ssd-boundary.sb";sb.write_text(runtime_profile())
    service={"Label":LABEL,"ProgramArguments":["/usr/bin/sandbox-exec","-f",str(sb),str(BASE/".venv/bin/python"),"-m","assistant.service"],
        "WorkingDirectory":str(BASE),"EnvironmentVariables":{"PYTHONPATH":str(BASE),"PYTHONUNBUFFERED":"1","PERSONAL_AI_SEATBELT":"1"},
        "RunAtLoad":True,"KeepAlive":True,"ThrottleInterval":15,
        "StandardOutPath":str(STATE/"logs/server.log"),"StandardErrorPath":str(STATE/"logs/server-error.log"),
        "ProcessType":"Background","ExitTimeOut":10,"Umask":63}
    if load().get('filesystem',{}).get('mode')=='full':
        service['ProgramArguments']=[str(BASE/'.venv/bin/python'),'-m','assistant.service']
        service['EnvironmentVariables'].pop('PERSONAL_AI_SEATBELT',None)
    client={"Label":"local.personal-ai.desktop","ProgramArguments":["/usr/bin/open","-a",str(BASE/"Jarvis.app")],"RunAtLoad":True}
    agents=Path.home()/"Library/LaunchAgents";agents.mkdir(parents=True,exist_ok=True)
    for data in (service,client):
        name=data["Label"]+".plist";payload=plistlib.dumps(data)
        (STATE/name).write_bytes(payload)
        dest=agents/name
        if dest.exists() and dest.read_bytes()!=payload:
            # These names are project-specific; preserve any displaced version.
            shutil.copy2(dest,STATE/(name+".previous"))
        dest.write_bytes(payload);dest.chmod(0o600)
    command=["/bin/launchctl","bootstrap",DOMAIN,str(agents/(LABEL+".plist"))]
    for attempt in range(15):
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode==0:break
        # launchd can briefly retain a stopped job while its children exit.
        time.sleep(.3)
    else:raise RuntimeError("Could not load login service: "+result.stderr.strip())
    print("Installed user-login services. Open:",BASE/"Jarvis.app")

def main():
    p=argparse.ArgumentParser(prog="personal-ai")
    sub=p.add_subparsers(dest="command",required=True)
    for cmd in ("setup","install","start","stop","restart","status","export","backup","uninstall","reload-model"):sub.add_parser(cmd)
    chat=sub.add_parser("chat");chat.add_argument("text")
    pair=sub.add_parser("pair");pair.add_argument("name");pair.add_argument("--target")
    revoke=sub.add_parser("revoke");revoke.add_argument("device_id")
    lan=sub.add_parser("lan");lan.add_argument("mode",choices=["on","off"])
    idx=sub.add_parser("index");idx.add_argument("root");idx.add_argument("path")
    imp=sub.add_parser("import-memory");imp.add_argument("file",type=Path)
    restore=sub.add_parser("restore");restore.add_argument("file",type=Path)
    wake=sub.add_parser("set-wake");wake.add_argument("phrase");wake.add_argument("test_wav",type=Path)
    args=p.parse_args()
    if args.command=="setup":initialize();print("Initialized local settings and TLS")
    elif args.command=="install":install()
    elif args.command=="start":
        subprocess.run(["/bin/launchctl","bootstrap",DOMAIN,str(Path.home()/"Library/LaunchAgents"/(LABEL+".plist"))],check=True)
    elif args.command=="stop":subprocess.run(["/bin/launchctl","bootout",DOMAIN+"/"+LABEL],check=True)
    elif args.command=="restart":subprocess.run(["/bin/launchctl","kickstart","-k",DOMAIN+"/"+LABEL],check=True)
    elif args.command=="status":print(json.dumps(api("status"),indent=2))
    elif args.command=="chat":print(api("chat",{"text":args.text})["text"])
    elif args.command=="index":print(json.dumps(api("index",{"root":args.root,"path":args.path})))
    elif args.command=="pair":
        # Private local export, never a public pairing endpoint. A separate token
        # for each client and no host automation privileges by default.
        device=Database(STATE/"assistant.sqlite3").device(args.name)
        if args.target:
            if not args.target.replace("-","").isalnum() or len(args.target)>60 or args.target==load()["host_device"]:
                raise ValueError("Choose a unique alphanumeric target name, for example mac-mini")
            cfg=load();cfg.setdefault("companions",{})
            if args.target in cfg["companions"]:raise ValueError("Target is already registered")
            cfg["companions"][args.target]=device["id"];save(cfg)
            device["target"]=args.target
        out=BASE/"device-connections";out.mkdir(exist_ok=True,mode=0o700)
        target=out/(device["id"]+".json")
        from .network import connection_url
        private(target,json.dumps({**device,"server":connection_url(),"fingerprint":(STATE/"tls/fingerprint.txt").read_text()},indent=2).encode())
        print("Device credential saved privately:",target)
        if args.target:print("Restart the host service to register this companion target")
        print("Transfer it directly to the intended device; do not share it in chat or email.")
    elif args.command=="revoke":
        with Database(STATE/"assistant.sqlite3").connect() as c:
            c.execute("DELETE FROM devices WHERE id=? AND admin=0",(args.device_id,))
        print("Revoked remote device (host administrator is protected)")
    elif args.command=="lan":
        cfg=load();cfg["host"]="lan" if args.mode=="on" else "127.0.0.1";save(cfg)
        print("LAN setting saved. Restart the service to apply. TLS and per-device tokens remain required.")
    elif args.command=="export":
        out=BASE/"exports";out.mkdir(exist_ok=True,mode=0o700)
        f=out/("memory-"+uuid.uuid4().hex[:8]+".json")
        private(f,json.dumps(Database(STATE/"assistant.sqlite3").export(),indent=2).encode());print(f)
    elif args.command=="import-memory":
        # Only explicit local operator input; not reachable from an LLM tool.
        from .storage import Root
        try:relative=str(args.file.absolute().relative_to(BASE))
        except ValueError:raise BoundaryError("Import from internal project storage only")
        raw=Root(BASE).read(relative,10_000_000)
        if len(raw)>10_000_000:raise ValueError("Import exceeds 10 MB")
        data=json.loads(raw);db=Database(STATE/"assistant.sqlite3")
        for m in data.get("memories",[]):
            if isinstance(m.get("text"),str) and 0<len(m["text"])<=2000:db.memory(m["text"])
        for m in data.get("messages",[]):
            if m.get("role") in ("user","assistant") and isinstance(m.get("content"),str):
                db.add("imported", "local-import",m["role"],m["content"])
        print("Imported conversation text and chosen memories; no devices or executable configuration imported")
    elif args.command=="backup":
        db=Database(STATE/"assistant.sqlite3");name="assistant-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")+".sqlite3"
        tmp=STATE/name;db.backup(tmp)
        try:
            root=bound_root(STATE/"storage.json");root.write_new("backups/"+name,tmp.read_bytes());print(root.path/"backups"/name)
        finally:tmp.unlink(missing_ok=True)
    elif args.command=="restore":
        # Stop first. Never restore a DB while the service holds WAL connections.
        status=subprocess.run(["/bin/launchctl","print",DOMAIN+"/"+LABEL],capture_output=True)
        if status.returncode==0:raise RuntimeError("Stop the assistant before restoring")
        from .storage import Root
        try:relative=str(args.file.absolute().relative_to(BASE))
        except ValueError:raise BoundaryError("Restore from internal project storage only")
        raw=Root(BASE).read(relative,500_000_000)
        copy=STATE/("restore-input-"+uuid.uuid4().hex+".sqlite3")
        private(copy,raw)
        connection=sqlite3.connect("file:"+str(copy)+"?mode=ro",uri=True)
        if connection.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Invalid database")
        Database(STATE/"assistant.sqlite3").backup(STATE/("before-restore-"+uuid.uuid4().hex[:8]+".sqlite3"))
        with sqlite3.connect(STATE/"assistant.sqlite3") as dest:connection.backup(dest)
        connection.close();copy.unlink();print("Restored; start the assistant")
    elif args.command=="reload-model":
        import httpx
        with httpx.Client(timeout=10,trust_env=False) as c:
            c.post(load()["ollama_url"]+"/api/generate",json={"model":load()["model"],"keep_alive":0}).raise_for_status()
        print("Model unloaded; next request reloads it")
    elif args.command=="set-wake":
        if not 2<=len(args.phrase)<=60 or not all(c.isalpha() or c.isspace() for c in args.phrase):
            raise ValueError("Use a short phrase containing letters and spaces")
        from .storage import Root
        from .voice import Speech
        import numpy as np
        try:relative=str(args.test_wav.absolute().relative_to(BASE))
        except ValueError:raise BoundaryError("Place the wake test recording inside the internal project folder")
        speech=Speech();audio=speech.decode_wav(Root(BASE).read(relative,1_000_000))
        kws=speech.kws(args.phrase);stream=kws.create_stream();detected=False
        audio=np.concatenate([audio,np.zeros(24000,dtype=np.float32)])
        for offset in range(0,len(audio),1600):
            stream.accept_waveform(16000,audio[offset:offset+1600])
            while kws.is_ready(stream):
                kws.decode_stream(stream)
                if kws.get_result(stream):detected=True
        if not detected:raise RuntimeError("Detector did not recognize this phrase; configuration preserved")
        cfg=load();cfg["voice"]["wake_phrase"]=args.phrase;save(cfg)
        print("Wake phrase recognized in the provided test. Restart the service to apply.")
    elif args.command=="uninstall":
        for label in (LABEL,"local.personal-ai.desktop"):
            subprocess.run(["/bin/launchctl","bootout",DOMAIN+"/"+label],capture_output=True)
            path=Path.home()/"Library/LaunchAgents"/(label+".plist")
            if path.exists() and path.read_bytes()==(STATE/(label+".plist")).read_bytes():path.unlink()
        print("Login services removed. Source, memory, credentials and SSD data preserved for deliberate removal.")

if __name__=="__main__":main()
