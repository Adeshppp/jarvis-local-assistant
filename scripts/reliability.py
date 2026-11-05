"""Deployment recovery checks. Simulates missing SSD identity; never unmounts it."""
import json
import os
from pathlib import Path
import subprocess
import time
from assistant.cli import api
from assistant.config import BASE,STATE

result={}
def restart():subprocess.run([str(BASE/"jarvis"),"restart"],check=True)
def wait_online(expected,timeout=45):
    deadline=time.monotonic()+timeout
    last=None
    while time.monotonic()<deadline:
        try:
            last=api("status")
            if last["runtime_online"] is expected and last["ssd_online"] is expected:return last
        except Exception:pass
        time.sleep(.5)
    raise RuntimeError("Service did not reach expected state: "+str(last and last["runtime_status"]))

initial=wait_online(True)
restart();wait_online(True)
result["service_restart_and_runtime_recovery"]=True
binding=STATE/"storage.json";original=binding.read_bytes()
try:
    changed=json.loads(original);changed["volume_uuid"]="SIMULATED-DISCONNECTED-VOLUME"
    binding.write_text(json.dumps(changed));restart();state=wait_online(False)
    result["simulated_ssd_identity_mismatch_disables_access"]=True
    try:api("chat",{"text":"Hello","conversation":"offline-test"})
    except Exception:result["offline_model_returns_error"]=True
    else:raise AssertionError("Inference unexpectedly succeeded with SSD access disabled")
finally:
    binding.write_bytes(original);binding.chmod(0o600);restart()
wait_online(True);result["ssd_identity_restored_and_runtime_recovered"]=True
subprocess.run([str(BASE/"jarvis"),"backup"],check=True)
result["sqlite_backup_to_owned_ssd_folder"]=True
samples=[]
for i in range(3):
    raw=subprocess.run(["/bin/ps","-axo","pid,ppid,rss,%cpu,comm"],capture_output=True,text=True).stdout
    samples.append([line.strip() for line in raw.splitlines() if str(BASE) in line or "ollama" in line])
    if i<2:time.sleep(5)
result["idle_process_samples"]=samples
result["swap"]=subprocess.run(["/usr/sbin/sysctl","vm.swapusage"],capture_output=True,text=True).stdout
result["physical_ssd_detachment_tested"]=False
result["actual_logout_login_cycle_tested"]=False
(BASE/"docs/reliability-checks.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
