import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = lambda: os.environ.get("MAPA_DB", str(ROOT / "data" / "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS obligations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 code TEXT UNIQUE NOT NULL,
 duty_code TEXT NOT NULL, step_no INTEGER NOT NULL DEFAULT 1, role TEXT,
 subject TEXT NOT NULL, organ TEXT NOT NULL, act_type TEXT NOT NULL, area TEXT,
 kind TEXT NOT NULL, applicability TEXT DEFAULT 'always',
 conditions TEXT, exceptions TEXT, follow_up TEXT,
 deadline_kind TEXT DEFAULT 'none', deadline_dates TEXT, deadline_months INTEGER, deadline_text TEXT,
 prep_days INTEGER DEFAULT 14, gap_days INTEGER DEFAULT 0,
 documents TEXT, agenda_title TEXT, resolution_text TEXT,
 trigger_key TEXT, keywords TEXT,
 status TEXT NOT NULL, verify_reason TEXT,
 source_name TEXT, source_ref TEXT, source_version TEXT, effective_from TEXT, verified_on TEXT,
 is_demo INTEGER DEFAULT 0, content_hash TEXT, batch_id INTEGER, updated_at TEXT,
 responsible TEXT, submitter TEXT, nature TEXT, approvers TEXT
);
CREATE INDEX IF NOT EXISTS ix_ob_duty ON obligations(duty_code, step_no);
CREATE TABLE IF NOT EXISTS meetings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, organ TEXT NOT NULL, date TEXT NOT NULL, time TEXT, note TEXT,
 UNIQUE(organ, date));
CREATE TABLE IF NOT EXISTS programs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, organ TEXT NOT NULL, meeting_date TEXT NOT NULL,
 covers_until TEXT, answers_json TEXT, items_json TEXT, updated_at TEXT,
 UNIQUE(organ, meeting_date));
CREATE TABLE IF NOT EXISTS imports(
 id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, sha256 TEXT, imported_at TEXT,
 created INTEGER, updated INTEGER, unchanged INTEGER, skipped INTEGER);
CREATE TABLE IF NOT EXISTS previews(token TEXT PRIMARY KEY, payload TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


def connect():
    Path(DB_PATH()).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH(), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    cols = {r[1] for r in c.execute("PRAGMA table_info(obligations)")}
    for col in ("responsible", "submitter", "nature", "approvers"):   # migrace starších databází
        if col not in cols:
            c.execute(f"ALTER TABLE obligations ADD COLUMN {col} TEXT")
    c.commit()
    return c


def get_setting(db, key, default=None):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(db, key, value):
    db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))
    db.commit()
