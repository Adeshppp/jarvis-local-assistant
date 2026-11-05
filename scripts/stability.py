"""Bounded conversation and explicit persistent-memory retrieval test."""
import json
import time
import uuid
from assistant.cli import api,local_token
from assistant.config import BASE,STATE
import httpx,ssl

conversation="stability-"+uuid.uuid4().hex[:8]
prompts=["Answer briefly: what is a compiler?","What is an interpreter?","How are they different?","Give a short Python example.","Explain what that example prints.","What verification color did I explicitly save in memory?"]
ctx=ssl.create_default_context(cafile=str(STATE/"tls/ca.pem"))
headers={"Authorization":"Bearer "+local_token()}
for attempt in range(60):
    try:
        if api("status")["runtime_online"]:break
    except Exception:pass
    time.sleep(.5)
else:raise RuntimeError("Assistant did not become ready")
with httpx.Client(verify=ctx,timeout=90,trust_env=False) as c:
    r=c.post("https://localhost:8765/api/memory",headers=headers,json={"text":"Assistant installation verification color: cobalt."});r.raise_for_status();ident=r.json()["id"]
    results=[]
    try:
        for prompt in prompts:
            result=api("chat",{"text":prompt,"conversation":conversation})
            results.append({"prompt":prompt,"answer":result["text"],"metrics":result["metrics"]})
            print('Verified turn',len(results),flush=True)
        assert "cobalt" in results[-1]["answer"].lower()
    finally:c.delete("https://localhost:8765/api/memory/"+ident,headers=headers).raise_for_status()
(BASE/"docs/conversation-stability.json").write_text(json.dumps({"turns":results,"saved_memory_retrieved":True,"scope":"Six-turn bounded functional check; not a thermal soak or multi-hour benchmark"},indent=2))
