import json
import sqlite3
import time
import pytest
from pydantic import ValidationError
from assistant.config import defaults
from assistant.db import Database
from assistant.tools import Tools
from assistant.storage import BoundaryError

@pytest.fixture
def setup(tmp_path):
    db=Database(tmp_path/"db.sqlite3");cfg=defaults();inbox=tmp_path/"inbox";inbox.mkdir();cfg["approved_roots"]={"inbox":str(inbox)}
    local=db.device("host",True);remote=db.device("phone")
    return db,cfg,Tools(cfg,db),db.authenticate(local["token"]),db.authenticate(remote["token"])

def test_persistence_and_safe_search(setup):
    db,*_=setup
    db.add("main","host","user","The cobalt cat likes astronomy")
    assert db.search("cobalt")[0]["role"]=="user"
    assert db.search('" OR * syntax')==[]
    ident=db.memory("I prefer short answers")
    fresh=Database(db.path);assert fresh.memories()[0]["id"]==ident
    fresh.memory("I prefer longer answers",ident)
    assert len(fresh.memories())==1

def test_backup_is_consistent(setup,tmp_path):
    db,*_=setup;db.memory("persistent")
    target=tmp_path/"backup.sqlite3";db.backup(target)
    with sqlite3.connect(target) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert c.execute("SELECT text FROM memories").fetchone()[0]=="persistent"

def test_authentication_and_device_identity(setup):
    db,_,_,local,remote=setup
    assert local["id"]!=remote["id"]
    assert db.authenticate("wrong") is None
    with db.connect() as c:c.execute("DELETE FROM devices WHERE id=?",(remote["id"],))
    assert db.authenticate("wrong") is None

def test_no_arbitrary_shell_or_extra_arguments(setup):
    _,_,tools,local,_=setup
    with pytest.raises(BoundaryError):tools.request("shell",{"command":"echo bad"},local)
    with pytest.raises(ValidationError):tools.request("system_info",{"command":"bad"},local)

def test_remote_has_no_automation_permissions(setup):
    _,_,tools,_,remote=setup
    with pytest.raises(BoundaryError):tools.request("launch_application",{"name":"TextEdit"},remote)
    assert tools.request("system_info",{},remote)["machine"]

def test_wrong_device_never_falls_back_to_host(setup):
    _,_,tools,local,_=setup
    with pytest.raises(BoundaryError,match="no authorized companion"):tools.request("system_info",{"target":"mac-mini"},local)

def test_approval_is_bound_and_single_use(setup,monkeypatch):
    db,_,tools,local,remote=setup;calls=[]
    monkeypatch.setattr(tools,"execute",lambda name,a,d:calls.append((name,a,d)) or {"ok":True})
    requested=tools.request("launch_application",{"name":"TextEdit"},local)
    assert calls==[]
    with pytest.raises(BoundaryError):tools.approve(requested["id"],True,remote)
    assert tools.approve(requested["id"],True,local)=={"ok":True}
    assert len(calls)==1
    with pytest.raises(BoundaryError):tools.approve(requested["id"],True,local)
    assert len(calls)==1

def test_denial_and_expiry_do_not_execute(setup,monkeypatch):
    db,_,tools,local,_=setup
    monkeypatch.setattr(tools,"execute",lambda *_:pytest.fail("Should never execute"))
    a=tools.request("launch_application",{"name":"TextEdit"},local)
    assert tools.approve(a["id"],False,local)=={"denied":True}
    b=tools.request("launch_application",{"name":"Calculator"},local)
    with db.connect() as c:c.execute("UPDATE approvals SET expires=0 WHERE id=?",(b["id"],))
    with pytest.raises(BoundaryError):tools.approve(b["id"],True,local)

def test_changed_definition_or_revoked_requester_cannot_execute(setup,monkeypatch):
    db,cfg,tools,local,_=setup
    monkeypatch.setattr(tools,"execute",lambda *_:pytest.fail("Should never execute"))
    a=tools.request("launch_application",{"name":"TextEdit"},local)
    cfg["applications"]["TextEdit"]="/different/application"
    assert "changed" in tools.approve(a["id"],True,local)["error"]
    b=tools.request("launch_application",{"name":"Calculator"},local)
    with db.connect() as c:c.execute("DELETE FROM devices WHERE id=?",(local["id"],))
    assert "revoked" in tools.approve(b["id"],True,local)["error"]

def test_root_read_scopes(setup,tmp_path):
    _,cfg,tools,local,_=setup
    (tmp_path/"inbox/note.txt").write_text("my note")
    assert tools.request("read_file",{"root":"inbox","path":"note.txt"},local)["untrusted_data"]=="my note"
    cfg["approved_roots"]["bad"]="/Volumes/Sandisk"
    with pytest.raises(BoundaryError):tools.root("bad")
    with pytest.raises(BoundaryError):tools.request("read_file",{"root":"inbox","path":"../outside"},local)
