"""Optional real-browser integration on an app-owned synthetic form, not a user's account."""
import os
from pathlib import Path
import pytest
from assistant.config import defaults
from assistant.db import Database
from assistant.tools import Tools
from assistant.webtools import Browser

pytestmark=pytest.mark.skipif(not os.environ.get('JARVIS_BROWSER_BINARIES'),reason='Set JARVIS_BROWSER_BINARIES to run real Chromium integration')

def test_browser_form_actions_wait_for_approval_and_reject_stale_page(tmp_path):
    cfg=defaults();cfg['filesystem']={'mode':'full'}
    db=Database(tmp_path/'db');d=db.device('test owner',True);device=db.authenticate(d['token'])
    tools=Tools(cfg,db)
    tools.browser.executor.shutdown(wait=False)
    browser=Browser(state=tmp_path/'browser-state',headless=True,binaries=os.environ['JARVIS_BROWSER_BINARIES'])
    tools.browser=browser
    try:
        browser.call('navigate',url='https://www.python.org/')
        html='''<html><title>Jarvis synthetic form</title><body><input id="entry"><p id="result">not clicked</p><button id="apply" type="button" onclick="document.getElementById('result').textContent=document.getElementById('entry').value">Apply fixture</button><input id="secret" type="password"></body></html>'''
        browser.executor.submit(lambda:browser.page.set_content(html)).result()
        fill=tools.request('browser',{'action':'fill','selector':'#entry','text':'fixture value'},device)
        assert browser.executor.submit(lambda:browser.page.input_value('#entry')).result()==''
        result=tools.approve(fill['id'],True,device);assert 'error' not in result,result
        assert browser.executor.submit(lambda:browser.page.input_value('#entry')).result()=='fixture value'
        click=tools.request('browser',{'action':'click','selector':'#apply'},device)
        assert 'not clicked' in browser.call('read')['untrusted_data']
        result=tools.approve(click['id'],True,device);assert 'fixture value' in result['untrusted_data']
        secret=tools.request('browser',{'action':'fill','selector':'#secret','text':'test-only'},device)
        assert 'takeover' in tools.approve(secret['id'],True,device).get('error','') or browser.executor.submit(lambda:browser.page.input_value('#secret')).result()==''
        pending=tools.request('browser',{'action':'click','selector':'#apply'},device)
        browser.call('navigate',url='https://example.com/')
        assert 'changed' in tools.approve(pending['id'],True,device)['error']
    finally:browser.shutdown()
