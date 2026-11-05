import asyncio
from types import SimpleNamespace
import pytest
from assistant.companion import execute
from assistant.companions import Companions
from assistant.config import defaults
from assistant.db import Database
from assistant.tools import Tools
from assistant.storage import BoundaryError

def test_companion_only_has_fixed_tools():
    assert execute({"tool":"system_info","arguments":{"target":"mac-mini"}},"mac-mini",[])["device"]=="mac-mini"
    assert "error" in execute({"tool":"shell","arguments":{"target":"mac-mini","command":"bad"}},"mac-mini",[])
    assert "error" in execute({"tool":"system_info","arguments":{"target":"host"}},"mac-mini",[])
    assert "error" in execute({"tool":"launch_application","arguments":{"target":"mac-mini","name":"Calculator"}},"mac-mini",[])

def test_remote_routing_does_not_execute_on_host(tmp_path):
    db=Database(tmp_path/"db");d=db.device("host",True);device=db.authenticate(d["token"])
    tools=Tools(defaults(),db)
    class Remote:
        def connected(self,target):return target=="mac-mini"
        def call(self,target,name,arguments):return {"device":target,"remote":True}
    tools.remote=Remote()
    assert tools.request("system_info",{"target":"mac-mini"},device)=={"device":"mac-mini","remote":True}
    with pytest.raises(BoundaryError):tools.request("system_info",{"target":"other-mac"},device)

def test_unregistered_companion_is_rejected(tmp_path):
    db=Database(tmp_path/"db");cfg=defaults();hub=Companions(cfg,db)
    async def run():
        with pytest.raises(BoundaryError):await hub.session(None,{"id":"untrusted"},"mac-mini")
    asyncio.run(run())

def test_hub_matches_response_to_target_and_device(tmp_path):
    db=Database(tmp_path/"db");device=db.device("mini");hub=Companions(defaults(),db)
    class Wire:
        async def send_json(self,packet):
            target,future=hub.pending[packet["id"]]
            assert target=="mac-mini"
            future.set_result({"device":"mac-mini","system":"Darwin"})
    async def run():
        hub.connections["mac-mini"]={"ws":Wire(),"device":device["id"]}
        assert (await hub.dispatch("mac-mini","system_info",{}))["device"]=="mac-mini"
        with db.connect() as c:c.execute("DELETE FROM devices WHERE id=?",(device["id"],))
        with pytest.raises(BoundaryError):await hub.dispatch("mac-mini","system_info",{})
    asyncio.run(run())
