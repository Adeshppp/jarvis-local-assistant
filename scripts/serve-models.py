"""Temporary foreground Ollama server for the manual first-time model install."""
import subprocess
from assistant.config import BASE
from assistant.service import ollama_env,runtime_profile
try:
    subprocess.run(['/usr/bin/sandbox-exec','-p',runtime_profile(),str(BASE/'vendor/ollama/ollama'),'serve'],env=ollama_env(),check=True)
except KeyboardInterrupt:
    pass
