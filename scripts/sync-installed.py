"""Copy reviewed source into my private install without replacing state or models."""
from pathlib import Path
import argparse
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('--destination',type=Path,default=Path.home()/'Library/Application Support/PersonalAI-Local')
args=parser.parse_args()
source=Path(__file__).resolve().parent.parent
destination=args.destination.expanduser().absolute()
if destination.parent!=Path.home()/'Library/Application Support' or not destination.name.startswith('PersonalAI-Local') or destination.is_symlink():
    raise ValueError('Choose the existing private PersonalAI-Local installation')
if source==destination:
    print('This checkout is already the installed source; no copy is needed.')
    raise SystemExit(0)
if not (destination/'state/config.json').is_file():
    raise ValueError('Existing installation not found; follow the fresh installation guide first')
for name in ('assistant','scripts','native','web','tests','docs'):
    ignored=['__pycache__']
    if name=='docs':ignored.extend(['*.json','*-tests.txt','test-results.txt'])
    shutil.copytree(source/name,destination/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns(*ignored))
for name in ('jarvis','pyproject.toml','requirements.lock','README.md','AGENTS.md','ARCHITECTURE.md','CHAT_CONTEXT.md','FUTURE_DEVELOPMENT.md','.gitignore'):
    shutil.copy2(source/name,destination/name)
print('Copied source. Existing configuration, credentials, SQLite data and models were preserved.')
