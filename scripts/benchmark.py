from pathlib import Path
import json
import subprocess
import time
import httpx
import argparse

base=Path(__file__).resolve().parent.parent
url="http://127.0.0.1:11435"
parser=argparse.ArgumentParser();parser.add_argument("--model",default="qwen3.5:4b");args=parser.parse_args()
model=args.model
cases=[
    ("cold","Reply in one short sentence: what is the capital of France?"),
    ("warm","In two sentences, explain why the sky is blue."),
    ("structured","Reply with JSON only containing the sum of 17 and 25 under key sum."),
]
report={"model":model,"context":4096,"generated_limit":160,"runs":[]}
with httpx.Client(timeout=180,trust_env=False) as client:
    report["model_info"]=client.post(url+"/api/show",json={"model":model}).json()
    for label,text in cases:
        start=time.perf_counter();first=None;answer="";final={}
        with client.stream("POST",url+"/api/chat",json={"model":model,"messages":[{"role":"user","content":text}],"think":False,"stream":True,"options":{"num_ctx":4096,"num_predict":160,"temperature":0},"keep_alive":"3m"}) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:continue
                item=json.loads(line)
                if item.get("error"):raise RuntimeError(item["error"])
                part=item.get("message",{}).get("content","")
                if part and first is None:first=time.perf_counter()-start
                answer+=part
                if item.get("done"):final=item
        run={"case":label,"answer":answer,"wall_seconds":time.perf_counter()-start,"first_token_seconds":first,
             "load_seconds":final.get("load_duration",0)/1e9,"eval_tokens":final.get("eval_count"),
             "tokens_per_second":final.get("eval_count",0)/max(final.get("eval_duration",1)/1e9,.001)}
        report["runs"].append(run);print(json.dumps(run),flush=True)
    report["resident_models"]=client.get(url+"/api/ps").json()
    schema={"type":"function","function":{"name":"system_info","description":"Get this Mac's system info","parameters":{"type":"object","properties":{},"additionalProperties":False}}}
    r=client.post(url+"/api/chat",json={"model":model,"messages":[{"role":"user","content":"Use the system_info tool to report the host OS."}],"tools":[schema],"think":False,"stream":False,"options":{"num_ctx":4096,"num_predict":120,"temperature":0}})
    r.raise_for_status();report["tool_call"]=r.json();print('Tool calling:',r.json().get('message'),flush=True)
report["swap"]=subprocess.run(["/usr/sbin/sysctl","vm.swapusage"],capture_output=True,text=True).stdout
processes=subprocess.run(["/bin/ps","-axo","pid,comm,rss,%cpu"],capture_output=True,text=True).stdout
report["processes"]="\n".join(line for line in processes.splitlines() if "ollama" in line or "llama-server" in line or "PersonalAI" in line)
(base/"docs"/("inference-benchmark-"+model.replace(":","-")+".json")).write_text(json.dumps(report,indent=2))
