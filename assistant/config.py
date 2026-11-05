from __future__ import annotations
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATE = BASE / "state"

def load() -> dict:
    return json.loads((STATE / "config.json").read_text())

def save(config: dict):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = STATE / "config.json"
    temp = STATE / "config.new"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)
    os.replace(temp, target)

def defaults() -> dict:
    return {"host": "127.0.0.1", "port": 8765, "host_device": "macbook-air",
            "model": "qwen3.5:2b", "models": ["qwen3.5:2b"],
            "ollama_url": "http://127.0.0.1:11435", "context": 4096,
            "max_tokens": 320, "keep_alive": "3m", "retention_days": 90,
            "approved_roots": {"inbox": str(BASE / "inbox")},
            "filesystem":{"mode":"restricted","ssd_mount":"/Volumes/Sandisk"},
            "web":{"headless":False},
            "applications": {"TextEdit": "/System/Applications/TextEdit.app",
                             "Calculator": "/System/Applications/Calculator.app"},
            "actions": {}, "voice": {"wake_phrase": "Hey Jarvis", "enabled": False,
            "input_device": None, "output_device": None, "voice": "Samantha", "rate": 185,
            "follow_up_seconds": 8, "max_record_seconds": 20, "silence_seconds": 1.0,
            "energy_threshold": 0.012, "muted": True}}
