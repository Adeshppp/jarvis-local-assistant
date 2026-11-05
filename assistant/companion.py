"""Run on an authorized secondary Mac. No local AI runtime is needed.

Only system_info and explicitly enabled Apple app launches exist. The companion
has no filesystem, credential, scripting, or arbitrary command endpoint.
"""
import argparse
import json
from pathlib import Path
import platform
import ssl
import subprocess
import time
from websockets.sync.client import connect

APPS={"Calculator":"/System/Applications/Calculator.app","TextEdit":"/System/Applications/TextEdit.app"}

def execute(packet,target,allowed):
    args=packet.get("arguments",{})
    if args.get("target")!=target:return {"error":"Target mismatch"}
    if packet.get("tool")=="system_info":
        return {"system":platform.system(),"version":platform.mac_ver()[0],"machine":platform.machine(),"device":target}
    if packet.get("tool")=="launch_application":
        name=args.get("name")
        if name not in allowed or name not in APPS:return {"error":"Application is not enabled in the local companion"}
        p=subprocess.run(["/usr/bin/open","-a",APPS[name]],capture_output=True,timeout=10)
        return {"launched":name,"device":target} if p.returncode==0 else {"error":"Local application launch failed"}
    return {"error":"This companion does not implement that tool"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--config",required=True,type=Path)
    p.add_argument("--allow-app",choices=APPS,action="append",default=[])
    args=p.parse_args();cfg=json.loads(args.config.read_text())
    if not cfg["server"].startswith("https://"):raise ValueError("HTTPS is required")
    context=ssl.create_default_context(cafile=str(args.config.parent/"server-certificate.pem"))
    url="wss://"+cfg["server"][8:]+"/companion"
    while True:
        try:
            with connect(url,ssl=context,open_timeout=10,max_size=65536) as ws:
                ws.send(json.dumps({"token":cfg["token"],"target":cfg["target"]}))
                first=json.loads(ws.recv(timeout=10))
                if not first.get("connected"):raise RuntimeError("Companion registration failed")
                print("Companion connected as",cfg["target"],flush=True)
                for raw in ws:
                    packet=json.loads(raw)
                    try:result=execute(packet,cfg["target"],args.allow_app)
                    except Exception as e:result={"error":str(e)[:200]}
                    ws.send(json.dumps({"id":packet["id"],"result":result}))
        except KeyboardInterrupt:break
        except Exception as e:
            print("Companion unavailable:",type(e).__name__,"— retrying",flush=True);time.sleep(3)

if __name__=="__main__":main()
