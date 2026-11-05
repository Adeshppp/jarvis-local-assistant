from __future__ import annotations
import datetime
import ipaddress
import json
import os
from pathlib import Path
import socket
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .config import BASE, STATE, defaults, save
from .db import Database

def private(path, data):
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as f: f.write(data)

def initialize():
    STATE.mkdir(exist_ok=True,mode=0o700)
    STATE.chmod(0o700)
    (BASE / "inbox").mkdir(exist_ok=True,mode=0o700)
    (STATE / "logs").mkdir(exist_ok=True,mode=0o700)
    if not (STATE / "config.json").exists(): save(defaults())
    db = Database(STATE / "assistant.sqlite3")
    with db.connect() as c: count = c.execute("SELECT count(*) FROM devices").fetchone()[0]
    if not count:
        device = db.device("MacBook Air",True,list(__import__("assistant.tools",fromlist=["DEFS"]).DEFS))
        private(STATE / "bootstrap-token",device["token"].encode())
        private(STATE / "local-device.json",json.dumps({"id":device["id"],"name":device["name"]}).encode())
    tls = STATE / "tls"
    tls.mkdir(exist_ok=True,mode=0o700)
    if (tls / "server.pem").exists() and (tls / "ca.pem").exists(): return
    now = datetime.datetime.now(datetime.timezone.utc)
    if (tls/"server.pem").exists():
        # Preserve the original installation certificate before upgrading to a
        # separate CA and correctly constrained TLS server certificate.
        previous=STATE/("tls-before-upgrade-"+now.strftime("%Y%m%d-%H%M%S"))
        previous.mkdir(mode=0o700)
        import shutil
        for file in tls.iterdir():
            if file.is_file():shutil.copy2(file,previous/file.name);file.unlink()
    ca_key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"Jarvis private device CA")])
    ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
        .not_valid_after(now+datetime.timedelta(days=1825))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),True)
        .add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,content_commitment=False,
            data_encipherment=False,key_agreement=False,key_cert_sign=True,crl_sign=True,encipher_only=False,decipher_only=False),True)
        .sign(ca_key,hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"Personal AI private server")])
    san = [x509.DNSName("localhost"),x509.DNSName(socket.gethostname()),x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        import subprocess
        for interface in ("en0","en1"):
            p = subprocess.run(["/usr/sbin/ipconfig","getifaddr",interface],capture_output=True,text=True)
            if p.returncode == 0: san.append(x509.IPAddress(ipaddress.ip_address(p.stdout.strip())))
        local=subprocess.run(["/usr/sbin/scutil","--get","LocalHostName"],capture_output=True,text=True)
        if local.returncode==0 and local.stdout.strip():san.append(x509.DNSName(local.stdout.strip()+".local"))
    except (OSError,ValueError): pass
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
            .not_valid_after(now+datetime.timedelta(days=365)).add_extension(x509.SubjectAlternativeName(san),False)
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),False)
            .add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=True,content_commitment=False,
                data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=False,decipher_only=False),True)
            .sign(ca_key,hashes.SHA256()))
    private(tls/"ca-key.pem",ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    private(tls/"ca.pem",ca.public_bytes(serialization.Encoding.PEM))
    (tls/"ca.der").write_bytes(ca.public_bytes(serialization.Encoding.DER))
    private(tls/"server-key.pem",key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    private(tls/"server.pem",cert.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))
    (tls/"server.der").write_bytes(cert.public_bytes(serialization.Encoding.DER))
    (tls/"fingerprint.txt").write_text(cert.fingerprint(hashes.SHA256()).hex())

if __name__ == "__main__": initialize()
