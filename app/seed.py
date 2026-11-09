"""Načtení syntetických demo dat (jen pokud je databáze prázdná)."""
import json
import sys
from pathlib import Path

from . import importer
from .db import ROOT, connect

DATA = ROOT / "data"


def seed_if_empty(db, force=False):
    if not force and db.execute("SELECT COUNT(*) FROM obligations").fetchone()[0]:
        return False
    from datetime import date
    csvp = DATA / "demo_map.csv"
    pv = importer.build_preview(db, "demo_map.csv", csvp.read_bytes(), date.today())
    importer.commit(db, pv["token"])
    if not db.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]:
        for m in json.loads((DATA / "demo_meetings.json").read_text(encoding="utf-8")):
            db.execute("INSERT OR IGNORE INTO meetings(organ,date,time,note) VALUES(?,?,?,?)",
                       (m["organ"], m["date"], m.get("time"), m.get("note", "DEMO")))
    db.commit()
    return True


if __name__ == "__main__":
    db = connect()
    if "--reset" in sys.argv:
        for t in ("obligations", "meetings", "programs", "imports", "previews"):
            db.execute(f"DELETE FROM {t}")
        db.commit()
    print("seeded" if seed_if_empty(db) else "database already has data")
