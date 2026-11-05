from __future__ import annotations
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid

class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, name TEXT NOT NULL,
              token_hash TEXT UNIQUE NOT NULL, admin INTEGER NOT NULL, tools TEXT NOT NULL,
              created REAL NOT NULL, last_seen REAL);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation TEXT NOT NULL,
              device TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS msg_conv ON messages(conversation,id);
            CREATE VIRTUAL TABLE IF NOT EXISTS message_fts USING fts5(content, content=messages, content_rowid=id);
            CREATE TRIGGER IF NOT EXISTS msg_insert AFTER INSERT ON messages BEGIN
              INSERT INTO message_fts(rowid,content) VALUES(new.id,new.content); END;
            CREATE TRIGGER IF NOT EXISTS msg_delete AFTER DELETE ON messages BEGIN
              INSERT INTO message_fts(message_fts,rowid,content) VALUES('delete',old.id,old.content); END;
            CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, text TEXT NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, device TEXT NOT NULL,
              tool TEXT NOT NULL, args TEXT NOT NULL, status TEXT NOT NULL, expires REAL NOT NULL,
              result TEXT, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, device TEXT, tool TEXT,
              status TEXT, detail TEXT, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, root TEXT, path TEXT, text TEXT, updated REAL);
            CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(id UNINDEXED, text);
            ''')
        path.chmod(0o600)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def device(self, name: str, admin=False, tools=None):
        token = secrets.token_urlsafe(36)
        ident = uuid.uuid4().hex
        with self.connect() as c:
            c.execute("INSERT INTO devices VALUES(?,?,?,?,?,?,?)", (ident,name,
                      hashlib.sha256(token.encode()).hexdigest(),int(admin),
                      json.dumps(tools or ["system_info","history_search","document_search"]),time.time(),None))
        return {"id": ident, "name": name, "token": token}

    def authenticate(self, token: str):
        if len(token) > 200: return None
        with self.connect() as c:
            r = c.execute("SELECT * FROM devices WHERE token_hash=?",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if not r: return None
            c.execute("UPDATE devices SET last_seen=? WHERE id=?",(time.time(),r["id"]))
            d = dict(r); d.pop("token_hash"); d["tools"] = json.loads(d["tools"])
            return d

    def add(self, conv, device, role, content):
        with self.connect() as c:
            c.execute("INSERT INTO messages(conversation,device,role,content,created) VALUES(?,?,?,?,?)",
                      (conv,device,role,content[:32000],time.time()))

    def history(self, conv, limit=16):
        with self.connect() as c:
            return [dict(r) for r in reversed(c.execute("SELECT * FROM messages WHERE conversation=? ORDER BY id DESC LIMIT ?",(conv,limit)).fetchall())]

    @staticmethod
    def query(text):
        terms = [x for x in text.replace('"',' ').split() if x.isalnum()][:12]
        return " OR ".join('"'+x+'"' for x in terms) or '"__empty__"'

    def search(self, text, limit=6):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT m.id,m.conversation,m.role,substr(m.content,1,1800) content FROM message_fts f JOIN messages m ON m.id=f.rowid WHERE message_fts MATCH ? ORDER BY rank LIMIT ?",(self.query(text),limit))]

    def memories(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM memories ORDER BY updated DESC LIMIT 200")]

    def memory(self, text, ident=None):
        ident = ident or uuid.uuid4().hex
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO memories VALUES(?,?,?)",(ident,text,time.time()))
        return ident

    def event(self, device, tool, status, detail):
        with self.connect() as c:
            c.execute("INSERT INTO events(device,tool,status,detail,created) VALUES(?,?,?,?,?)",(device,tool,status,str(detail)[:2000],time.time()))

    def export(self):
        with self.connect() as c:
            return {table:[dict(r) for r in c.execute("SELECT * FROM "+table)] for table in ("messages","memories")}

    def backup(self, destination: Path):
        with self.connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        destination.chmod(0o600)
