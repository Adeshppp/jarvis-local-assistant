"""Fixed read-only action: no user files, environment secrets or network access."""
import json
import platform
import sys
print(json.dumps({"system":platform.system(),"macos":platform.mac_ver()[0],"architecture":platform.machine(),"python":sys.version.split()[0]}))
