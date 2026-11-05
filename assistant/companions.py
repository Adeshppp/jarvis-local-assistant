"""Per-device, authenticated routing. An offline target never falls back to host."""
import asyncio
import json
import uuid
from .storage import BoundaryError

class Companions:
    def __init__(self, config, db):
        self.config,self.db=config,db
        self.connections={}
        self.pending={}
        self.loop=None

    def connected(self,target):return target in self.connections

    def call(self,target,name,arguments):
        if not self.loop or not self.connected(target):raise BoundaryError("Target companion is offline")
        future=asyncio.run_coroutine_threadsafe(self.dispatch(target,name,arguments),self.loop)
        return future.result(timeout=35)

    async def dispatch(self,target,name,arguments):
        connection=self.connections.get(target)
        if not connection:raise BoundaryError("Target companion is offline")
        with self.db.connect() as c:
            active=c.execute("SELECT id FROM devices WHERE id=?",(connection["device"],)).fetchone()
        if not active:raise BoundaryError("Companion device was revoked")
        ident=uuid.uuid4().hex;future=asyncio.get_running_loop().create_future()
        self.pending[ident]=(target,future)
        try:
            await connection["ws"].send_json({"id":ident,"tool":name,"arguments":arguments})
            return await asyncio.wait_for(future,30)
        finally:self.pending.pop(ident,None)

    async def session(self,ws,device,target):
        if self.config.get("companions",{}).get(target)!=device["id"] or target in self.connections:
            raise BoundaryError("This device is not registered for the requested target")
        self.loop=asyncio.get_running_loop()
        self.connections[target]={"ws":ws,"device":device["id"]}
        try:
            await ws.send_json({"connected":target})
            while True:
                packet=await ws.receive_json()
                if len(json.dumps(packet))>16000:raise BoundaryError("Companion result exceeds size limit")
                pending=self.pending.get(packet.get("id"))
                if pending and pending[0]==target and not pending[1].done():
                    result=packet.get("result")
                    if not isinstance(result,dict):result={"error":"Invalid companion response"}
                    pending[1].set_result(result)
        finally:
            self.connections.pop(target,None)
            for registered,future in list(self.pending.values()):
                if registered==target and not future.done():future.set_exception(BoundaryError("Target companion disconnected"))
