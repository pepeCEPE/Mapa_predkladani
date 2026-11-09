import csv
import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPA_DB", str(tmp_path / "t.db"))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


def make_csv(rows):
    from app.importer import NATIVE_FIELDS
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=NATIVE_FIELDS, delimiter=";")
    w.writeheader()
    for r in rows:
        d = dict.fromkeys(NATIVE_FIELDS, "")
        d.update(r)
        w.writerow(d)
    return buf.getvalue().encode("utf-8-sig")


def import_bytes(client, name, data):
    pv = client.post("/api/import/preview", files={"file": (name, data)}).json()
    return pv, client.post("/api/import/commit", json={"token": pv["token"]}).json()


OK = dict(zdroj="TEST", clanek="čl. 1", verze="1", ucinnost_od="2026-01-01", overeno_dne="2026-11-01", stav="potvrzeno")
