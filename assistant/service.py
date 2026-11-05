from __future__ import annotations
import asyncio
import contextlib
import json
import os
import signal
import subprocess
import ipaddress
import socket
from .config import BASE, STATE, load
from .storage import bound_root

def runtime_profile() -> str:
    binding=json.loads((STATE/"storage.json").read_text())
    root=json.dumps(binding["root"])
    return '(version 1)\n(allow default)\n(deny file-read* file-write* (subpath "/Volumes"))\n(allow file-read* file-write* (subpath '+root+'))\n(allow file-read-metadata (literal "/Volumes") (literal '+json.dumps(binding["volume"])+'))\n'

def profile() -> str:
    # The model runtime stays isolated. Personal tools are deliberately enabled
    # separately by the operator and remain subject to macOS/TCC permissions.
    return '(version 1)\n(allow default)\n' if load().get('filesystem',{}).get('mode')=='full' else runtime_profile()

def ollama_env():
    root=bound_root(STATE/"storage.json")
    path=root.runtime_path("models/llm")
    env=dict(os.environ)
    env.update(OLLAMA_HOST="127.0.0.1:11435",OLLAMA_MODELS=path,
               OLLAMA_NO_CLOUD="1",OLLAMA_NUM_PARALLEL="1",OLLAMA_MAX_LOADED_MODELS="1",
               OLLAMA_CONTEXT_LENGTH="4096",OLLAMA_KEEP_ALIVE="3m",OLLAMA_FLASH_ATTENTION="1")
    return env

class Runtime:
    def __init__(self): self.process=None; self.task=None; self.status="starting"; self.log=None

    async def monitor(self):
        while True:
            try:
                env=await asyncio.to_thread(ollama_env)
                if self.process is None or self.process.poll() is not None:
                    if self.log:self.log.close()
                    self.log=open(STATE/"logs/ollama.log","ab",buffering=0)
                    command=[str(BASE/"vendor/ollama/ollama"),"serve"]
                    if os.environ.get("PERSONAL_AI_SEATBELT")!="1":command=["/usr/bin/sandbox-exec","-p",runtime_profile()]+command
                    self.process=subprocess.Popen(command,env=env,stdout=self.log,stderr=subprocess.STDOUT)
                self.status="online" if self.process.poll() is None else "runtime failed; see logs"
            except Exception as e:
                self.status="SSD unavailable: "+str(e)[:180]
                self.stop_process()
            await asyncio.sleep(10)

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.process=None

    async def start(self): self.task=asyncio.create_task(self.monitor())
    async def stop(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):await self.task
        await asyncio.to_thread(self.stop_process)
        if self.log:self.log.close()

def main():
    import uvicorn
    cfg=load()
    if cfg["host"] not in ("127.0.0.1","lan"):
        raise ValueError("Only loopback or explicitly enabled LAN mode is supported")
    os.umask(0o077)
    settings=uvicorn.Config("assistant.server:app",host="127.0.0.1",port=cfg["port"],
                ssl_certfile=str(STATE/"tls/server.pem"),ssl_keyfile=str(STATE/"tls/server-key.pem"),
                access_log=False,log_level="info",timeout_keep_alive=5,limit_concurrency=16,ws_max_size=65536)
    addresses=["127.0.0.1"]
    if cfg["host"]=="lan":
        for interface in ("en0","en1"):
            p=subprocess.run(["/usr/sbin/ipconfig","getifaddr",interface],capture_output=True,text=True)
            try:address=ipaddress.ip_address(p.stdout.strip())
            except ValueError:continue
            if address.is_private and not address.is_loopback and str(address) not in addresses:addresses.append(str(address))
    sockets=[]
    for address in addresses:
        connection=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        connection.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        connection.bind((address,cfg["port"]));connection.listen(32);connection.setblocking(False)
        sockets.append(connection)
    uvicorn.Server(settings).run(sockets=sockets)

if __name__=="__main__":main()
