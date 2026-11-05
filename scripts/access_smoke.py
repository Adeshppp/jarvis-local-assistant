"""Verify the new capabilities using only task-owned file fixtures."""
from pathlib import Path
import json,ssl,time,uuid
import httpx
from assistant.cli import local_token
from assistant.config import BASE,STATE,load
from assistant.storage import bound_root

context=ssl.create_default_context(cafile=str(STATE/'tls/ca.pem'))
headers={'Authorization':'Bearer '+local_token()}
url='https://localhost:8765/api/'
ident='jarvis-access-'+uuid.uuid4().hex[:8]
directory=STATE/'tool-fixtures'/ident;directory.mkdir(parents=True,mode=0o700)
file=directory/'sample-note.txt';file.write_text('The verification word is cobalt.\n')
protected_dir=Path.home()/'Documents/Jarvis-Test-Fixtures'
protected_dir.mkdir(exist_ok=True)
protected=protected_dir/('protected-'+ident+'.txt')
protected.write_text('Only this assistant-created Documents fixture is being read.\n')
report={'fixture_directory':str(directory),'preexisting_ssd_contents_accessed':False}
with httpx.Client(verify=context,timeout=180,trust_env=False) as client:
 def call(path,body=None,method=None):
    r=client.request(method or ('POST' if body is not None else 'GET'),url+path,headers=headers,json=body)
    if r.status_code>=400:raise RuntimeError(str(r.status_code)+' '+r.text[:500])
    return r.json()
 for _ in range(60):
    try:
      status=call('status')
      if status['runtime_online']:break
    except Exception:pass
    time.sleep(.5)
 else:raise RuntimeError('Backend did not become ready')
 assert status['filesystem_mode']=='full'
 report['enabled_tools']=status['tools'];report['model']=status['model']
 def tool(name,arguments):return call('tools',{'name':name,'arguments':arguments})
 def approve(a):
    assert a.get('approval_required'),a
    return call('approvals/'+a['id'],{'allow':True})
 report['read']=tool('read_file',{'path':str(file)})
 assert 'cobalt' in report['read']['untrusted_data']
 report['protected_documents_read']=tool('read_file',{'path':str(protected)})
 report['filename_search']=tool('search_files',{'query':'sample-note','path':str(directory)})
 assert any(r['path']==str(file) for r in report['filename_search']['matches'])
 proposed=tool('edit_file',{'path':str(file),'old_text':'cobalt','new_text':'indigo'})
 assert 'cobalt' in file.read_text()
 report['approved_edit']=approve(proposed);assert 'indigo' in file.read_text(),report['approved_edit']
 moved=directory/('renamed-'+ident+'.txt')
 report['approved_move']=approve(tool('move_file',{'path':str(file),'destination':str(moved)}));assert moved.exists() and not file.exists()
 report['opened_original']=tool('open_file',{'path':str(moved)})
 report['trash']=approve(tool('delete_file',{'path':str(moved)}));assert not moved.exists(),report['trash']
 trashed=report['trash']['trash_location']
 assert tool('read_file',{'path':trashed})['untrusted_data'].endswith('indigo.\n')
 report['fixture_trash_cleanup']=approve(tool('delete_file',{'path':trashed,'permanent':True}))
 # SSD fixtures are strictly inside the newly created assistant project root.
 root=bound_root(STATE/'storage.json');relative='temporary/'+ident;root.mkdir(relative)
 root.write_new(relative+'/ssd-note.txt',b'assistant-created SSD fixture')
 ssd_file=root.path/relative/'ssd-note.txt'
 report['ssd_read']=tool('read_file',{'path':str(ssd_file)})
 report['ssd_search']=tool('search_files',{'query':'ssd-note','path':str(ssd_file.parent)})
 report['ssd_edit']=approve(tool('edit_file',{'path':str(ssd_file),'old_text':'fixture','new_text':'fixture verified'}))
 assert root.read(relative+'/ssd-note.txt').endswith(b'fixture verified')
 # Real model tool selection; no personal file content or broad SSD search.
 report['model_file_read']=call('chat',{'text':'Read the file '+str(protected)+' and tell me its first sentence. Use read_file.','conversation':ident})
 assert any(t['tool']=='read_file' for t in report['model_file_read']['tools']),report['model_file_read']
 assert 'Only this assistant-created Documents fixture is being read' in report['model_file_read']['text'],report['model_file_read']
 report['web_search']=tool('web_search',{'query':'Python official documentation','limit':3,'open_browser':False})
 assert report['web_search'].get('untrusted_results'),report['web_search']
 report['read_webpage']=tool('read_webpage',{'url':'https://www.python.org/'})
 report['visible_browser']=tool('open_url',{'url':'https://www.python.org/'})
 assert 'Python' in report['visible_browser']['title']
 report['browser_close']=tool('browser',{'action':'close'})
 report['unauthenticated_status']=client.get(url+'status').status_code
 assert report['unauthenticated_status']==401
(BASE/'docs/access-update-tests.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:report[k] for k in ['model','enabled_tools','approved_edit','approved_move','trash','ssd_edit','model_file_read','unauthenticated_status']},indent=2))
print('Verified protected fixture, approved changes, owned SSD fixture, live search and visible browser.',flush=True)
