"""Ask macOS about the active sandbox policy without opening SSD contents."""
import ctypes
import json
import os
from assistant.config import STATE,BASE

b=json.loads((STATE/"storage.json").read_text())
library=ctypes.CDLL("/usr/lib/libsandbox.1.dylib")
check=library.sandbox_check
check.restype=ctypes.c_int
check.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
paths={"project":b["root"],"volume_root":b["volume"],
       "outside_project":b["volume"]+"/__policy_test_no_file_access__"}
result={}
for label,path in paths.items():
    result[label]={}
    for operation in ("file-read-data","file-write-create"):
        denied=check(os.getpid(),operation.encode(),ctypes.c_int(1),ctypes.c_char_p(path.encode()))
        result[label][operation]="denied" if denied else "allowed"
assert result["project"]["file-read-data"]=="allowed",result
assert result["volume_root"]["file-read-data"]=="denied",result
assert result["outside_project"]["file-read-data"]=="denied",result
assert result["outside_project"]["file-write-create"]=="denied",result
(BASE/"docs/os-sandbox-check.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
