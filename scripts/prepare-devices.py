"""Generate public certificate enrollment materials. No tokens embedded."""
import json
import plistlib
from pathlib import Path
import socket
import uuid
from assistant.config import BASE,STATE
from assistant.network import connection_url
out=BASE/"device-connections"
out.mkdir(exist_ok=True,mode=0o700)
cert=(STATE/"tls/ca.der").read_bytes()
payload={"PayloadType":"com.apple.security.root","PayloadVersion":1,
         "PayloadIdentifier":"local.personal-ai.certificate","PayloadUUID":str(uuid.uuid4()).upper(),
         "PayloadDisplayName":"Personal AI private server certificate","PayloadContent":cert}
profile={"PayloadType":"Configuration","PayloadVersion":1,
         "PayloadIdentifier":"local.personal-ai.trust","PayloadUUID":str(uuid.uuid4()).upper(),
         "PayloadDisplayName":"Jarvis — your private server",
         "PayloadDescription":"Trust your own assistant's TLS certificate. Install only on devices you own. No cloud service or management enrollment.",
         "PayloadContent":[payload]}
(out/"Jarvis-Private-Server.mobileconfig").write_bytes(plistlib.dumps(profile))
(out/"server-certificate.pem").write_bytes((STATE/"tls/ca.pem").read_bytes())
(out/"server-fingerprint.txt").write_text((STATE/"tls/fingerprint.txt").read_text())
(out/"connection.json").write_text(json.dumps({"server":connection_url(),
        "fingerprint":(STATE/"tls/fingerprint.txt").read_text(),"authentication":"A unique per-device bearer token, provisioned locally with jarvis pair"},indent=2))
print("Prepared public certificate enrollment files:",out)
