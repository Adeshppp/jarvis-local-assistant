import io
import json
import os
import subprocess
from pathlib import Path
import pytest
from docx import Document
from openpyxl import Workbook,load_workbook
from assistant.config import defaults
from assistant.db import Database
from assistant.tools import Tools
from assistant.storage import BoundaryError
from assistant.webtools import public_url

@pytest.fixture(scope='session')
def file_helper(tmp_path_factory):
    directory=tmp_path_factory.mktemp('native-file-helper')
    helper=directory/'file-actions'
    source=Path(__file__).resolve().parents[1]/'native/FileActions.swift'
    subprocess.run(['/usr/bin/swiftc','-O','-module-cache-path',str(directory/'cache'),str(source),'-o',str(helper)],check=True,capture_output=True)
    return helper

@pytest.fixture
def personal(tmp_path,file_helper):
    cfg=defaults();cfg['filesystem']={'mode':'full','helper':str(file_helper)}
    db=Database(tmp_path/'state/db.sqlite3');d=db.device('owner',True)
    tools=Tools(cfg,db);tools.files.state=tmp_path/'state'
    yield tools,db,db.authenticate(d['token']),tmp_path
    tools.browser.executor.shutdown(wait=False)

def test_read_absolute_paths_and_symlinks_without_folder_allowlist(personal):
    tools,_,device,tmp=personal
    file=tmp/'ordinary.txt';file.write_text('user-visible data')
    alias=tmp/'alias.txt';alias.symlink_to(file)
    assert tools.request('read_file',{'path':str(alias)},device)['untrusted_data']=='user-visible data'
    assert tools.request('file_info',{'path':str(file)},device)['size']==17

def test_list_hidden_and_search_only_requested_fixture_tree(personal):
    tools,_,device,tmp=personal
    (tmp/'.hidden-note.txt').write_text('cobalt needle')
    listing=tools.request('list_directory',{'path':str(tmp)},device)
    assert any(e['name']=='.hidden-note.txt' for e in listing['items'])
    result=tools.files.search('hidden',path=str(tmp),use_index=False)
    assert any(e['name']=='.hidden-note.txt' for e in result['matches'])
    content=tools.files.search('cobalt',path=str(tmp),content=True,use_index=False)
    assert any('cobalt' in e.get('excerpt','') for e in content['matches'])

def test_text_edit_is_previewed_and_atomic_with_undo(personal):
    tools,_,device,tmp=personal;file=tmp/'note.txt';file.write_text('before\n');file.chmod(0o640)
    requested=tools.request('edit_file',{'path':str(file),'old_text':'before','new_text':'after'},device)
    assert requested['approval_required'] and 'diff' in requested['preview']
    assert file.read_text()=='before\n'
    result=tools.approve(requested['id'],True,device)
    assert file.read_text()=='after\n',result
    assert file.stat().st_mode&0o777==0o640
    assert (Path(result['undo_record']).parent/'original').read_text()=='before\n'
    with pytest.raises(BoundaryError):tools.approve(requested['id'],True,device)

def test_changed_target_rejects_old_approval(personal):
    tools,_,device,tmp=personal;file=tmp/'note.txt';file.write_text('before')
    a=tools.request('edit_file',{'path':str(file),'old_text':'before','new_text':'after'},device)
    file.write_text('changed in another app')
    assert 'changed' in tools.approve(a['id'],True,device)['error']
    assert file.read_text()=='changed in another app'

def test_new_file_and_rename_do_not_overwrite(personal):
    tools,_,device,tmp=personal;file=tmp/'new.txt'
    a=tools.request('write_file',{'path':str(file),'content':'created'},device)
    assert not file.exists();r=tools.approve(a['id'],True,device);assert file.read_text()=='created',r
    with pytest.raises(FileExistsError):tools.request('write_file',{'path':str(file),'content':'bad'},device)
    destination=tmp/'renamed.txt'
    a=tools.request('move_file',{'path':str(file),'destination':str(destination)},device)
    assert file.exists();r=tools.approve(a['id'],True,device)
    assert destination.read_text()=='created' and not file.exists(),r

def test_destination_created_after_preview_is_preserved(personal):
    tools,_,device,tmp=personal;file=tmp/'source';file.write_text('original');dest=tmp/'destination'
    a=tools.request('move_file',{'path':str(file),'destination':str(dest)},device);dest.write_text('someone else')
    assert 'changed' in tools.approve(a['id'],True,device)['error']
    assert file.read_text()=='original' and dest.read_text()=='someone else'

def test_delete_defaults_to_trash_and_needs_approval(personal):
    tools,_,device,tmp=personal;file=tmp/'trash-fixture.txt';file.write_text('test-owned')
    a=tools.request('delete_file',{'path':str(file)},device)
    assert file.exists() and 'Trash' in a['preview']['method']
    r=tools.approve(a['id'],True,device);assert 'trashed' in r,r
    assert not file.exists()
    trashed=Path(r['trash_location']);assert trashed.read_text()=='test-owned'
    # Remove exactly our test-created item, never enumerate the user's Trash.
    trashed.unlink()

def test_permanent_delete_and_denial(personal):
    tools,_,device,tmp=personal;file=tmp/'only-fixture.txt';file.write_text('owned')
    a=tools.request('delete_file',{'path':str(file),'permanent':True},device)
    assert 'PERMANENT' in a['preview']['method'];assert file.exists()
    tools.approve(a['id'],False,device);assert file.exists()
    a=tools.request('delete_file',{'path':str(file),'permanent':True},device)
    assert 'permanently_deleted' in tools.approve(a['id'],True,device)
    assert not file.exists()

def test_symlink_swap_cannot_edit_another_file(personal):
    tools,_,device,tmp=personal;file=tmp/'file.txt';file.write_text('before');other=tmp/'other.txt';other.write_text('untouched')
    a=tools.request('edit_file',{'path':str(file),'old_text':'before','new_text':'after'},device)
    file.unlink();file.symlink_to(other)
    assert 'error' in tools.approve(a['id'],True,device)
    assert other.read_text()=='untouched'

def test_credentials_read_requires_approval(personal):
    tools,_,device,tmp=personal;file=tmp/'.env';file.write_text('EXAMPLE=test-fixture')
    a=tools.request('read_file',{'path':str(file)},device)
    assert a['approval_required'] and 'untrusted_data' not in a
    assert tools.approve(a['id'],True,device)['untrusted_data']=='EXAMPLE=test-fixture'

def test_owned_remote_device_can_approve_only_its_own_request(personal):
    tools,db,_,tmp=personal
    phone=db.device('phone',tools=['write_file']);other=db.device('other',tools=['write_file'])
    phone=db.authenticate(phone['token']);other=db.authenticate(other['token'])
    a=tools.request('write_file',{'path':str(tmp/'from-phone'),'content':'approved'},phone)
    with pytest.raises(BoundaryError):tools.approve(a['id'],True,other)
    assert 'changed' in tools.approve(a['id'],True,phone)

def test_word_edit_preserves_other_run_and_repeatable_preview(personal):
    tools,_,device,tmp=personal;file=tmp/'test.docx'
    doc=Document();p=doc.add_paragraph();p.add_run('before').bold=True;p.add_run(' unchanged').italic=True;doc.save(file)
    a=tools.request('edit_file',{'path':str(file),'old_text':'before','new_text':'after'},device)
    assert 'before' in tools.files.read(str(file))['untrusted_data']
    r=tools.approve(a['id'],True,device);assert 'changed' in r,r
    changed=Document(file);assert changed.paragraphs[0].text=='after unchanged';assert changed.paragraphs[0].runs[-1].italic

def test_excel_cell_edit(personal):
    tools,_,device,tmp=personal;file=tmp/'test.xlsx';book=Workbook();book.active['A1']=10;book.active['B1']='keep';book.save(file)
    a=tools.request('edit_file',{'path':str(file),'sheet':'Sheet','cell':'A1','new_text':'42'},device)
    r=tools.approve(a['id'],True,device);assert 'changed' in r,r
    changed=load_workbook(file);assert changed.active['A1'].value==42;assert changed.active['B1'].value=='keep';changed.close()

@pytest.mark.parametrize('path',['/','/Users','/System','/Volumes',str(Path.home()),'/Volumes/SomeVolume'])
def test_whole_system_roots_are_not_trash_targets(personal,path):
    tools,_,device,_=personal
    with pytest.raises(BoundaryError):tools.request('delete_file',{'path':path},device)

@pytest.mark.parametrize('url',['file:///etc/passwd','javascript:alert(1)','https://user:secret@example.com','http://127.0.0.1','http://169.254.169.254','http://[::1]'])
def test_web_does_not_expose_local_admin_services(url):
    with pytest.raises(BoundaryError):public_url(url)

def test_tool_routing_exposes_the_requested_domain(personal):
    tools,_,device,_=personal
    names=lambda text:{s['function']['name'] for s in tools.schemas(device,text)}
    assert {'search_files','read_file','edit_file'}<=names('Find my document and edit the text')
    assert {'web_search','open_url','browser'}<=names('Open a browser and search the internet')
    assert 'search_files' not in names('Open a browser and search the internet')
    assert 'web_search' not in names('Search my SSD for a file')
    assert 'delete_file' not in names('Explain photosynthesis')
