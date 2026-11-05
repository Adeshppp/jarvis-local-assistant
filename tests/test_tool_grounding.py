import asyncio,json
import pytest
from assistant.config import defaults
from assistant.db import Database
from assistant.inference import Inference,context_result

def test_large_tool_text_keeps_its_real_content_field():
    r=context_result('read_file',{'path':'/some/note','offset':100,'untrusted_data':'a'*6000,'content_available':True})
    assert r['untrusted_data']=='a'*2500
    assert r['next_offset']==2600 and r['content_available']
    result=context_result('web_search',{'untrusted_results':[{'url':'https://example.com','title':'Real result','snippet':'a'*1000}],'browser':{'untrusted_data':'large page'}})
    assert result['untrusted_results'][0]['url']=='https://example.com' and 'browser' not in result

class Stream:
    def __init__(self,message):self.message=message
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    def raise_for_status(self):pass
    async def aiter_lines(self):
        yield json.dumps({'message':self.message,'done':True,'eval_count':10,'eval_duration':1000000000})

def fake_client(monkeypatch,messages):
    replies=iter(messages)
    class Client:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def stream(self,*args,**kwargs):return Stream(next(replies))
    monkeypatch.setattr('assistant.inference.httpx.AsyncClient',Client)

def test_successful_file_read_cannot_end_with_false_access_refusal(tmp_path,monkeypatch):
    db=Database(tmp_path/'db');d=db.device('owner',True);device=db.authenticate(d['token'])
    class Tools:
        def schemas(self,*args):return [{'type':'function','function':{'name':'read_file','parameters':{}}}]
        def request(self,*args):return {'path':'/fixture','untrusted_data':'Cobalt is the verification word.','read_authorized':True,'content_available':True}
    fake_client(monkeypatch,[{'tool_calls':[{'function':{'name':'read_file','arguments':{'path':'/fixture'}}}]},
        {'content':'I cannot access the actual contents, only metadata.'},
        {'content':'Cobalt is the verification word.'}])
    reply=asyncio.run(Inference(defaults(),db,Tools()).respond('Read /fixture and tell me its first sentence.','test',device))
    assert reply['text']=='Cobalt is the verification word.'

def test_document_cannot_invoke_a_tool_outside_the_request_schema(tmp_path,monkeypatch):
    db=Database(tmp_path/'db');d=db.device('owner',True);device=db.authenticate(d['token'])
    class Tools:
        def schemas(self,*args):return [{'type':'function','function':{'name':'read_webpage','parameters':{}}}]
        def request(self,*args):pytest.fail('Unadvertised destructive tool must not run')
    fake_client(monkeypatch,[{'tool_calls':[{'function':{'name':'delete_file','arguments':{'path':'/fixture'}}}]},{'content':'The action was blocked.'}])
    reply=asyncio.run(Inference(defaults(),db,Tools()).respond('Read the webpage.','test',device))
    assert 'not enabled' in reply['tools'][0]['result']['error']
