from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import json
import time
import uuid
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from .config import BASE, STATE, load, save
from .db import Database
from .inference import Inference
from .tools import Tools
from .storage import BoundaryError, bound_root
from .service import Runtime
from .voice import Speech, voice_session
from .companions import Companions

config=load()
db=Database(STATE/"assistant.sqlite3")
tools=Tools(config,db)
companions=Companions(config,db)
tools.remote=companions
inference=Inference(config,db,tools)
speech=Speech()
runtime=Runtime()
sessions={}

@asynccontextmanager
async def lifespan(app):
    with db.connect() as c:
        c.execute("DELETE FROM messages WHERE created<?",(time.time()-config["retention_days"]*86400,))
        c.execute("UPDATE approvals SET status='expired' WHERE status='pending' AND expires<?",(time.time(),))
    await runtime.start()
    yield
    await asyncio.to_thread(tools.browser.shutdown)
    await runtime.stop()

app=FastAPI(title="Personal AI",docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)

@app.middleware("http")
async def guards(request: Request,call_next):
    origin=request.headers.get("origin")
    if origin and origin!="https://"+request.headers.get("host",""):
        return JSONResponse({"error":"Cross-origin requests are forbidden"},403)
    length=request.headers.get("content-length","0")
    try:
        if int(length)>6_000_000:return JSONResponse({"error":"Request too large"},413)
    except ValueError:return JSONResponse({"error":"Invalid request"},400)
    if request.method in ("POST","PUT","PATCH"):
        data=bytearray()
        async for block in request.stream():
            data.extend(block)
            if len(data)>6_000_000:return JSONResponse({"error":"Request too large"},413)
        request._body=bytes(data)
    response=await call_next(request)
    response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff",
        "Referrer-Policy":"no-referrer","X-Frame-Options":"DENY",
        "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"})
    return response

def auth(authorization: str=Header(default="")):
    if not authorization.startswith("Bearer "):raise HTTPException(401,"Device token required")
    device=db.authenticate(authorization[7:])
    if not device:raise HTTPException(401,"Unknown or revoked device")
    return device

def admin(device=Depends(auth)):
    if not device["admin"]:raise HTTPException(403,"Host administrator required")
    return device

@app.exception_handler(BoundaryError)
async def boundary(request,exc):return JSONResponse({"detail":str(exc)},403)

@app.exception_handler(PermissionError)
async def file_permission(request,exc):
    return JSONResponse({'detail':'macOS denied this file operation. On the host Mac, use Jarvis → File access permissions… to grant the backend normal Full Disk Access. '+str(exc)},403)

@app.exception_handler(ValueError)
async def invalid_tool_value(request,exc):return JSONResponse({'detail':str(exc)},422)

@app.exception_handler(FileNotFoundError)
async def missing_file(request,exc):return JSONResponse({'detail':str(exc)},404)

@app.get("/")
def index():return FileResponse(BASE/"web/index.html")
@app.get("/app.js")
def javascript():return FileResponse(BASE/"web/app.js",media_type="application/javascript")
@app.get("/style.css")
def stylesheet():return FileResponse(BASE/"web/style.css",media_type="text/css")

@app.get("/api/status")
async def status(device=Depends(auth)):
    import httpx
    models=[];online=False
    try:
        async with httpx.AsyncClient(timeout=2,trust_env=False) as c:
            r=await c.get(config["ollama_url"]+"/api/ps");r.raise_for_status();models=r.json().get("models",[]);online=True
    except Exception:pass
    try:
        root=bound_root(STATE/"storage.json")
        import os
        fd=await asyncio.to_thread(root._anchor);os.close(fd);ssd=True
    except Exception:ssd=False
    with db.connect() as c:
        devices=[dict(r) for r in c.execute("SELECT id,name,last_seen FROM devices")]
        recent=[dict(r) for r in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT 15")]
        pending=[dict(r) for r in c.execute("SELECT id,tool,args,device,expires FROM approvals WHERE status='pending' AND expires>? AND (?=1 OR device=?)",(time.time(),device['admin'],device['id']))]
    active_model=inference.active_model if inference.active else models[0].get('name') if models else config['model']
    return {"device":device,"model":config["model"],"active_model":active_model,"tool_model":config.get('tool_model',config['model']),"runtime_online":online,
            "runtime_status":runtime.status,"ssd_online":ssd,"loaded_models":models,
            "busy":inference.active,"voice_sessions":sessions,"voice":config["voice"],"companions":list(companions.connections),
            "metrics":inference.last_metrics,"devices":devices,"events":recent,"approvals":pending,
            "filesystem_mode":config.get('filesystem',{}).get('mode','restricted'),"tools":[s['function']['name'] for s in tools.schemas(device)]}

@app.websocket("/companion")
async def companion(ws:WebSocket):
    await ws.accept()
    try:
        packet=await asyncio.wait_for(ws.receive_json(),5)
        device=db.authenticate(packet.get("token",""))
        if not device:await ws.close(code=1008);return
        await companions.session(ws,device,packet.get("target",""))
    except Exception:
        try:await ws.close(code=1008)
        except RuntimeError:pass

class Chat(BaseModel):
    model_config=ConfigDict(extra="forbid")
    text: str=Field(min_length=1,max_length=8000)
    conversation: str=Field(default="main",pattern=r"^[a-zA-Z0-9_-]{1,100}$")

@app.post("/api/chat")
async def chat(body: Chat,device=Depends(auth)):
    try:return await inference.respond(body.text,body.conversation,device)
    except Exception as e:raise HTTPException(503,str(e)[:500]) from e

@app.post("/api/cancel")
async def cancel(device=Depends(auth)):
    if inference.current_task and (device["admin"] or inference.owner==device["id"]):
        inference.current_task.cancel()
        return {"cancelled":True}
    return {"cancelled":False}

@app.post("/api/model/unload")
async def unload_model(device=Depends(admin)):
    if inference.active:raise HTTPException(409,"Cancel the active reply before unloading")
    import httpx
    async with httpx.AsyncClient(timeout=15,trust_env=False) as c:
        r=await c.post(config["ollama_url"]+"/api/generate",json={"model":config["model"],"keep_alive":0})
        r.raise_for_status()
    return {"unloaded":True}

@app.get("/api/history")
def history(conversation: str="main",device=Depends(auth)):
    return db.history(conversation,100)

@app.get("/api/search")
def search(q: str,device=Depends(auth)):
    if len(q)>200:raise HTTPException(422,"Query too long")
    return db.search(q)

class Memory(BaseModel):
    text: str=Field(min_length=1,max_length=2000)

@app.get("/api/memory")
def memories(device=Depends(auth)):return db.memories()
@app.post("/api/memory")
def remember(body: Memory,device=Depends(auth)):return {"id":db.memory(body.text)}
@app.put("/api/memory/{ident}")
def update_memory(ident:str,body:Memory,device=Depends(auth)):return {"id":db.memory(body.text,ident)}
@app.delete("/api/memory/{ident}")
def forget(ident: str,device=Depends(auth)):
    with db.connect() as c:c.execute("DELETE FROM memories WHERE id=?",(ident,))
    return {"deleted":True}
@app.get("/api/export")
def export(device=Depends(admin)):return db.export()

class ToolCall(BaseModel):
    name: str=Field(max_length=80)
    arguments: dict=Field(default_factory=dict)
@app.post("/api/tools")
def tool(body:ToolCall,device=Depends(auth)):return tools.request(body.name,body.arguments,device)

class Decision(BaseModel): allow: bool
@app.post("/api/approvals/{ident}")
def approve(ident:str,body:Decision,device=Depends(auth)):return tools.approve(ident,body.allow,device)

@app.get("/api/settings")
def settings(device=Depends(admin)):return config

@app.patch("/api/settings")
def update_settings(body:dict,device=Depends(admin)):
    allowed={"model","tool_model","context","max_tokens","voice","retention_days"}
    if set(body)-allowed:raise HTTPException(422,"This setting requires local configuration")
    if "model" in body and body["model"] not in config["models"]:raise HTTPException(422,"Model is not installed and allowlisted")
    if 'tool_model' in body and body['tool_model'] not in config['models']:raise HTTPException(422,'Tool model must be installed and allowlisted')
    for key,low,high in (("context",2048,8192),("max_tokens",32,1024),("retention_days",1,3650)):
        if key in body and (type(body[key]) is not int or not low<=body[key]<=high):raise HTTPException(422,"Invalid "+key)
    if "voice" in body:
        v=body["voice"]
        if not isinstance(v,dict) or set(v)-{"voice","rate","follow_up_seconds","energy_threshold","silence_seconds","max_record_seconds"}:
            raise HTTPException(422,"Wake phrases and hardware settings require local validation")
        limits={"rate":(80,300),"follow_up_seconds":(0,30),"energy_threshold":(.001,.2),"silence_seconds":(.3,3),"max_record_seconds":(3,25)}
        for k,(lo,hi) in limits.items():
            if k in v and (not isinstance(v[k],(float,int)) or not lo<=v[k]<=hi):raise HTTPException(422,"Invalid voice setting")
        if "voice" in v and (not isinstance(v["voice"],str) or len(v["voice"])>80):raise HTTPException(422,"Invalid voice name")
        body["voice"]={**config["voice"],**v}
    config.update(body);save(config)
    return {"saved":True}

class IndexFile(BaseModel):
    root:str=Field(max_length=80)
    path:str=Field(max_length=1000)
@app.post("/api/index")
def index_file(body:IndexFile,device=Depends(admin)):
    text=tools.root(body.root).read(body.path).decode("utf-8")
    ident=uuid.uuid5(uuid.NAMESPACE_URL,body.root+":"+body.path).hex
    with db.connect() as c:
        c.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?)",(ident,body.root,body.path,text,time.time()))
        c.execute("DELETE FROM document_fts WHERE id=?",(ident,))
        c.execute("INSERT INTO document_fts VALUES(?,?)",(ident,text))
    return {"indexed":ident}

@app.delete("/api/index/{ident}")
def remove_index(ident:str,device=Depends(admin)):
    with db.connect() as c:
        c.execute("DELETE FROM documents WHERE id=?",(ident,));c.execute("DELETE FROM document_fts WHERE id=?",(ident,))
    return {"deleted":True}

@app.post("/api/transcribe")
async def transcribe(request:Request,device=Depends(auth)):
    data=await request.body()
    if len(data)>1_000_000:raise HTTPException(413,"Recording too long")
    try:return {"text":await speech.transcribe(speech.decode_wav(data))}
    except ValueError as e:raise HTTPException(422,str(e)) from e

@app.websocket("/voice")
async def voice(ws:WebSocket):
    origin=ws.headers.get("origin")
    if origin and origin!="https://"+ws.headers.get("host",""):
        await ws.close(code=1008);return
    await ws.accept()
    try:
        packet=await asyncio.wait_for(ws.receive_json(),5)
        device=db.authenticate(packet.get("token",""))
        if not device:await ws.close(code=1008);return
        if device["id"] in sessions:await ws.close(code=1008);return
        await voice_session(ws,device,config,inference,speech,sessions)
    except Exception:
        try:await ws.close(code=1011)
        except RuntimeError:pass
