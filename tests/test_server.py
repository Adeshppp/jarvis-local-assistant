import importlib
import json
import sys
import pytest
from fastapi.testclient import TestClient
from assistant.config import defaults

@pytest.fixture
def server(tmp_path,monkeypatch):
    import assistant.config as config
    cfg=defaults();(tmp_path/"config.json").write_text(json.dumps(cfg))
    monkeypatch.setattr(config,"STATE",tmp_path)
    sys.modules.pop("assistant.server",None)
    module=importlib.import_module("assistant.server")
    async def noop():pass
    monkeypatch.setattr(module.runtime,"start",noop);monkeypatch.setattr(module.runtime,"stop",noop)
    local=module.db.device("host",True);remote=module.db.device("phone")
    with TestClient(module.app,base_url="https://testserver") as client:
        yield client,module,local,remote

@pytest.mark.parametrize("path",["history","memory","settings","export","search?q=test"])
def test_all_private_routes_require_auth(server,path):
    c,*_=server;assert c.get("/api/"+path).status_code==401

def headers(d):return {"Authorization":"Bearer "+d["token"]}

def test_authorized_history_and_memory(server):
    c,_,local,_=server;h=headers(local)
    r=c.post("/api/memory",json={"text":"user chose this"},headers=h);assert r.status_code==200
    assert c.get("/api/memory",headers=h).json()[0]["text"]=="user chose this"
    assert c.delete("/api/memory/"+r.json()["id"],headers=h).status_code==200
    assert c.get("/api/memory",headers=h).json()==[]

def test_nonadmin_cannot_change_policy_or_export(server):
    c,_,_,remote=server;h=headers(remote)
    assert c.get("/api/settings",headers=h).status_code==403
    assert c.get("/api/export",headers=h).status_code==403
    assert c.post("/api/approvals/unknown",json={"allow":True},headers=h).status_code==403

def test_model_unload_requires_admin(server):
    c,_,_,remote=server
    assert c.post("/api/model/unload").status_code==401
    assert c.post("/api/model/unload",headers=headers(remote)).status_code==403

def test_policy_changes_cannot_be_smuggled_into_settings(server):
    c,_,local,_=server;h=headers(local)
    for body in ({"approved_roots":{"all":"/"}},{"model":"remote-model:cloud"},{"context":1000000},{"voice":{"wake_phrase":"unvalidated phrase"}}):
        assert c.patch("/api/settings",json=body,headers=h).status_code==422

def test_origin_protection(server):
    c,_,local,_=server
    assert c.get("/api/history",headers={**headers(local),"Origin":"https://attacker.example"}).status_code==403

def test_websocket_bad_device_is_rejected(server):
    c,*_=server
    with c.websocket_connect("/voice") as ws:
        ws.send_json({"token":"invalid"})
        assert ws.receive()["type"]=="websocket.close"

def test_input_limits_and_no_shell_endpoint(server):
    c,_,local,_=server;h=headers(local)
    assert c.post("/api/chat",json={"text":"x"*8001},headers=h).status_code==422
    assert c.post("/api/tools",json={"name":"shell","arguments":{"command":"anything"}},headers=h).status_code==403
