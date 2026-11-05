"""Real installation checks; no cloud inference, personal document access, or tokens in logs."""
import json
from pathlib import Path
import ssl
import time
import wave
import uuid
import httpx
import numpy as np
from websockets.sync.client import connect
from assistant.cli import local_token
from assistant.config import BASE,STATE

context=ssl.create_default_context(cafile=str(STATE/"tls/ca.pem"))
token=local_token()
headers={"Authorization":"Bearer "+token}
url="https://localhost:8765"
report={}
for attempt in range(60):
    try:
        with httpx.Client(verify=context,timeout=2,trust_env=False) as check:
            state=check.get(url+"/api/status",headers=headers).json()
            if state.get("runtime_online"):break
    except Exception:pass
    time.sleep(.5)
else:raise RuntimeError("Assistant did not become ready for smoke checks")
with httpx.Client(verify=context,timeout=120,trust_env=False) as c:
    report["unauthenticated_status"]=c.get(url+"/api/status").status_code
    report["wrong_token_status"]=c.get(url+"/api/status",headers={"Authorization":"Bearer wrong"}).status_code
    assert report["unauthenticated_status"]==report["wrong_token_status"]==401
    r=c.get(url+"/api/status",headers=headers);r.raise_for_status();s=r.json()
    report["runtime_online"]=s["runtime_online"];report["ssd_online"]=s["ssd_online"]
    assert s["runtime_online"] and s["ssd_online"],s["runtime_status"]
    report["ssd_escape_status"]=c.post(url+"/api/tools",headers=headers,json={"name":"read_file","arguments":{"root":"ssd","path":"../never-opened"}}).status_code
    assert report["ssd_escape_status"]==403
    r=c.post(url+"/api/memory",headers=headers,json={"text":"Installation test: temporary memory"});r.raise_for_status();ident=r.json()["id"]
    assert any(m["id"]==ident for m in c.get(url+"/api/memory",headers=headers).json())
    c.delete(url+"/api/memory/"+ident,headers=headers).raise_for_status();report["memory_create_read_delete"]=True
    r=c.post(url+"/api/chat",headers=headers,json={"text":"Use system_info to get this Mac's current OS and architecture. Answer briefly.","conversation":"installation-"+uuid.uuid4().hex[:8]});r.raise_for_status()
    report["real_tool_chat"]=r.json();print('Tool chat:',json.dumps(r.json()),flush=True)
    assert any(t["tool"]=="system_info" for t in r.json()["tools"])
    r=c.post(url+"/api/tools",headers=headers,json={"name":"launch_application","arguments":{"name":"Calculator"}});r.raise_for_status();ident=r.json()["id"]
    r=c.post(url+"/api/approvals/"+ident,headers=headers,json={"allow":True});r.raise_for_status();report["approved_automation"]=r.json();assert r.json().get("launched")=="Calculator",r.json()
    replay=c.post(url+"/api/approvals/"+ident,headers=headers,json={"allow":True});report["approval_replay_status"]=replay.status_code;assert replay.status_code==403
    r=c.post(url+"/api/tools",headers=headers,json={"name":"registered_action","arguments":{"name":"Assistant diagnostic"}});r.raise_for_status();ident=r.json()["id"]
    r=c.post(url+"/api/approvals/"+ident,headers=headers,json={"allow":True});r.raise_for_status();report["registered_script"]=r.json();assert r.json().get("exit_code")==0,r.json()

def audio(name):
    with wave.open(str(BASE/"tests/fixtures"/name),"rb") as f:
        return np.frombuffer(f.readframes(f.getnframes()),dtype="<i2").astype(np.float32)/32768

with connect("wss://localhost:8765/voice",ssl=context,open_timeout=5,close_timeout=3) as ws:
    ws.send(json.dumps({"token":token}));initial=json.loads(ws.recv(timeout=5))
    ws.send(json.dumps({"action":"wake"}));print("Voice connected",flush=True)
    data=np.concatenate([np.zeros(8000,dtype=np.float32),audio("hey-jarvis.wav"),np.zeros(24000,dtype=np.float32)])
    for offset in range(0,len(data),1600):ws.send(data[offset:offset+1600].astype("<f4").tobytes())
    for _ in range(10):
        item=json.loads(ws.recv(timeout=15))
        if item["event"]=="error":raise RuntimeError(item)
        if item["event"]=="ack":report["wake_ack"]=item;break
    else:raise AssertionError("Wake acknowledgement missing")
    ws.send(json.dumps({"action":"spoken_done"}))
    data=np.concatenate([audio("question.wav"),np.zeros(24000,dtype=np.float32)])
    started=time.perf_counter()
    for offset in range(0,len(data),1600):ws.send(data[offset:offset+1600].astype("<f4").tobytes())
    for _ in range(15):
        item=json.loads(ws.recv(timeout=120))
        if item["event"]=="error":raise RuntimeError(item)
        if item["event"]=="transcript":report["voice_transcript"]=item["text"]
        if item["event"]=="speak":
            report["voice_reply"]=item;report["synthetic_voice_wall_seconds"]=time.perf_counter()-started;break
    else:raise AssertionError("Spoken reply payload missing")
    ws.send(json.dumps({"action":"mute"}))

report["limits"]="Synthetic microphone transport fixture; live microphone and actual acoustic speech output still require user verification."
(BASE/"docs/installation-smoke.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
