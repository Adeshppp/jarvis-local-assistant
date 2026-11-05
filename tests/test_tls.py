from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID
import assistant.setup as setup
import assistant.config as config

def test_generated_tls_has_server_auth_and_separate_ca(tmp_path,monkeypatch):
    monkeypatch.setattr(setup,"STATE",tmp_path/"state")
    monkeypatch.setattr(setup,"BASE",tmp_path)
    monkeypatch.setattr(config,"STATE",tmp_path/"state")
    setup.initialize()
    tls=tmp_path/"state/tls"
    cert=x509.load_der_x509_certificate((tls/"server.der").read_bytes())
    ca=x509.load_der_x509_certificate((tls/"ca.der").read_bytes())
    assert ExtendedKeyUsageOID.SERVER_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert cert.issuer==ca.subject
    assert "localhost" in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    assert (tls/"server-key.pem").stat().st_mode&0o777==0o600
