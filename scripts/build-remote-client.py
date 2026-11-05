"""Package a lightweight Apple Silicon client with public certificate pins only."""
from pathlib import Path
import json
import plistlib
import shutil
import subprocess
from assistant.config import BASE,STATE
from assistant.network import connection_url

target=BASE/"device-connections/JarvisClient.app"
if target.exists():shutil.rmtree(target)
shutil.copytree(BASE/"Jarvis.app",target)
resources=target/"Contents/Resources"
(resources/"remote-client.json").write_text(json.dumps({"server":connection_url()}))
for name in ("server.der","ca.der"):shutil.copy2(STATE/"tls"/name,resources/name)
info=target/"Contents/Info.plist";data=plistlib.loads(info.read_bytes());data["CFBundleIdentifier"]="local.personal-ai.client";data["CFBundleName"]="JarvisClient";info.write_bytes(plistlib.dumps(data))
subprocess.run(["/usr/bin/codesign","--force","--sign","-","--identifier","local.personal-ai.client",str(target)],check=True)
print("Packaged client (no embedded device token):",target)
