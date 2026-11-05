"""End-to-end natural-language requests; no personal files or signed-in web accounts."""
from assistant.cli import api
from assistant.config import BASE,STATE
import json,uuid

directory=STATE/'tool-fixtures/natural-requests';directory.mkdir(parents=True,exist_ok=True)
file=directory/'discovery-note.txt';file.write_text('The test color is indigo.\n')
report={}
report['natural_file_search']=api('chat',{'text':'Find discovery-note.txt inside '+str(directory)+'. Give me the full path.','conversation':'natural-'+uuid.uuid4().hex[:8]})
print('File result:',report['natural_file_search']['text'],flush=True)
assert any(t['tool'] in {'search_files','list_directory','file_info','read_file'} for t in report['natural_file_search']['tools']),report
assert str(file) in report['natural_file_search']['text'],report
report['natural_web_search']=api('chat',{'text':'Open a browser and search the web for the official Python documentation. Give me one official documentation link.','conversation':'natural-'+uuid.uuid4().hex[:8]})
print('Web result:',report['natural_web_search']['text'],flush=True)
assert any(t['tool'] in {'web_search','open_url','browser'} for t in report['natural_web_search']['tools']),report
assert 'python.org' in report['natural_web_search']['text'],report
api('tools',{'name':'browser','arguments':{'action':'close'}})
(BASE/'docs/natural-tool-tests.json').write_text(json.dumps(report,indent=2))
print('Natural-language file and web requests verified',flush=True)
