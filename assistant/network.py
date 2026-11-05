import subprocess

def connection_url():
    p=subprocess.run(["/usr/sbin/scutil","--get","LocalHostName"],capture_output=True,text=True,timeout=5)
    name=p.stdout.strip()
    if not name or p.returncode:raise RuntimeError("macOS local hostname is unavailable")
    return "https://"+name+".local:8765"
