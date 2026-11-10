from __future__ import annotations

from typing import Optional

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import engine as E
from . import importer, service as S
from .db import connect, get_setting, set_setting
from .search import search as run_search
from .textutil import norm

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    from .seed import seed_if_empty
    db = connect()
    seed_if_empty(db)
    db.close()
    yield


app = FastAPI(title="Mapa předkládání", version="0.1.0", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
ROOT = Path(__file__).resolve().parent.parent


def get_db():
    db = connect()
    try:
        yield db
    finally:
        db.close()


def _d(s, field="datum"):
    try:
        return E.parse_date(s)
    except ValueError:
        raise HTTPException(422, f"Neplatné {field}: {s}")


@app.get("/api/meta")
def meta(db=Depends(get_db)):
    n = db.execute("SELECT COUNT(*) c, SUM(is_demo) d, SUM(status='potvrzeno') ok FROM obligations").fetchone()
    cols = {c: sorted({r[0] for r in db.execute(f"SELECT DISTINCT {c} FROM obligations WHERE {c} IS NOT NULL AND {c}!=''")}) for c in ("act_type", "area")}
    return {"organs": E.ORGANS, "program_organs": E.PROGRAM_ORGANS, "checklist": S.CHECKLIST,
            "acts": cols["act_type"], "areas": cols["area"], "count": n["c"], "demo_count": n["d"] or 0,
            "confirmed_count": n["ok"] or 0,
            "has_meetings": db.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] > 0, "fy_end": S.fy_of(db), "today": E.iso(date.today())}


@app.put("/api/settings")
def settings(body: dict, db=Depends(get_db)):
    fy = str(body.get("fy_end", "12-31"))
    try:
        E.fy_end_date(2001, fy)
    except Exception:
        raise HTTPException(422, "fy_end musí mít tvar MM-DD")
    set_setting(db, "fy_end", fy)
    return {"fy_end": fy}


def _chain(db, duty_code, ref):
    steps = [S.public(s, ref) for s in S.groups(S.load_obligations(db)).get(duty_code, [])]
    return steps


@app.get("/api/search")
def search(q: str, today: Optional[str] = None, db=Depends(get_db)):
    t = S.today_of(today)
    obs = S.load_obligations(db)
    by_id = {o["id"]: o for o in obs}
    gs = S.groups(obs)
    res = []
    for g in run_search(obs, q):
        steps = gs[g["duty_code"]]
        first = steps[0]
        pub = [S.public(s, t) for s in steps]
        res.append({"duty_code": g["duty_code"], "subject": first["subject"], "score": round(g["score"], 2),
                    "via_synonym": g["via_synonym"], "matched_ids": g["matched"], "kind": first["kind"],
                    "confirmed": all(p["confirmed"] for p in pub), "is_demo": first["is_demo"],
                    "conditions": first["conditions"], "applicability": first["applicability"],
                    "deadline_text": next((s["deadline_text"] for s in steps if s["deadline_text"]), ""),
                    "agenda_title": first["agenda_title"], "steps": pub})
    return {"q": q, "count": len(res), "results": res}


@app.get("/api/obligations")
def obligations(q: str = "", organ: str = "", act_type: str = "", area: str = "", kind: str = "",
                status: str = "", limit: int = 50, offset: int = 0, today: Optional[str] = None, db=Depends(get_db)):
    t = S.today_of(today)
    obs = S.load_obligations(db)
    if q:
        ids = {i for g in run_search(obs, q) for i in g["matched"]}
        obs = [o for o in obs if o["id"] in ids]
    f = lambda o: ((not organ or o["organ"] == organ) and (not act_type or o["act_type"] == act_type)
                   and (not area or o["area"] == area) and (not kind or o["kind"] == kind)
                   and (not status or (status == "potvrzeno") == S.is_confirmed(o, t)))
    obs = [o for o in obs if f(o)]
    total = len(obs)
    return {"total": total, "items": [S.public(o, t) for o in obs[offset:offset + min(limit, 500)]]}


@app.get("/api/obligations/{oid}")
def obligation(oid: int, today: Optional[str] = None, db=Depends(get_db)):
    t = S.today_of(today)
    r = db.execute("SELECT * FROM obligations WHERE id=?", (oid,)).fetchone()
    if not r:
        raise HTTPException(404, "Pravidlo nenalezeno")
    ob = dict(r)
    steps = S.groups(S.load_obligations(db))[ob["duty_code"]]
    plan = None
    if ob["kind"] == "periodic" and any(E.has_deadline(s) for s in steps):
        plan = S.recommend(db, ob["duty_code"], None, t)
    elif ob["kind"] == "event":
        plan = S.recommend(db, ob["duty_code"], None, t)
    return {"obligation": S.public(ob, t), "chain": [S.public(s, t) for s in steps], "plan": plan}


@app.get("/api/meetings")
def meetings(db=Depends(get_db)):
    return [dict(r) | {"organ_label": E.ORGANS.get(r["organ"])} for r in db.execute("SELECT * FROM meetings ORDER BY date, organ")]


def _snapshot(db, today):
    out = {}
    for duty, steps in S.groups(S.load_obligations(db)).items():
        if steps[0]["kind"] == "periodic" and any(E.has_deadline(s) for s in steps):
            p = S.recommend(db, duty, None, today)
            out[duty] = (p["subject"], p["status"], p.get("best"))
    return out


@app.post("/api/meetings")
def add_meeting(body: dict, db=Depends(get_db)):
    organ, d = body.get("organ"), _d(body.get("date"))
    if organ not in E.ORGANS or not d:
        raise HTTPException(422, "Zadejte orgán a datum zasedání.")
    t = S.today_of(body.get("today"))
    before = _snapshot(db, t)
    try:
        db.execute("INSERT INTO meetings(organ,date,time,note) VALUES(?,?,?,?)", (organ, E.iso(d), body.get("time"), body.get("note")))
    except Exception:
        raise HTTPException(409, "Zasedání tohoto orgánu v tento den už existuje.")
    db.commit()
    return {"ok": True, "changed": _diff(before, _snapshot(db, t))}


@app.delete("/api/meetings/{mid}")
def del_meeting(mid: int, today: Optional[str] = None, db=Depends(get_db)):
    t = S.today_of(today)
    before = _snapshot(db, t)
    db.execute("DELETE FROM meetings WHERE id=?", (mid,))
    db.commit()
    return {"ok": True, "changed": _diff(before, _snapshot(db, t))}


def _diff(a, b):
    return [{"duty_code": k, "subject": b[k][0], "before": a.get(k, (None, None, None))[1:], "after": b[k][1:]}
            for k in b if a.get(k) != b[k]]


@app.post("/api/recommend")
def recommend(body: dict, db=Depends(get_db)):
    try:
        return S.recommend(db, body["duty_code"], _d(body.get("deadline")), S.today_of(body.get("today")))
    except KeyError:
        raise HTTPException(404, "Povinnost nenalezena")


@app.get("/api/dashboard")
def dashboard(today: Optional[str] = None, db=Depends(get_db)):
    return S.dashboard(db, S.today_of(today))


@app.get("/api/calendar")
def calendar(year: Optional[int] = None, today: Optional[str] = None, db=Depends(get_db)):
    t = S.today_of(today)
    y = year or t.year
    items = S.calendar_items(db, t, date(y, 1, 1), date(y, 12, 31))
    ms = [dict(r) | {"organ_label": E.ORGANS.get(r["organ"])} for r in
          db.execute("SELECT * FROM meetings WHERE date BETWEEN ? AND ? ORDER BY date", (f"{y}-01-01", f"{y}-12-31"))]
    return {"year": y, "items": items, "meetings": ms,
            "no_calendar": db.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 0,
            "incomplete": [o for o in E.PROGRAM_ORGANS if not any(m["organ"] == o for m in ms)]}


@app.post("/api/program/check")
def program_check(body: dict, db=Depends(get_db)):
    organ = body.get("organ")
    if organ not in E.PROGRAM_ORGANS:
        raise HTTPException(422, "Vyberte představenstvo, dozorčí radu nebo valnou hromadu.")
    md = _d(body.get("date"))
    if not md:
        raise HTTPException(422, "Zadejte datum zasedání.")
    answers = {k: norm(v) for k, v in (body.get("answers") or {}).items()}
    return S.check_program(db, organ, md, _d(body.get("covers_until")), answers, S.today_of(body.get("today")))


def _prog_text(p, items):
    lines = [f"Návrh programu – {E.ORGANS[p['organ']]}, {E.cz(p['meeting_date'])}", ""]
    for n, i in enumerate(items, 1):
        lines.append(f"{n}. {i['title']}" + (f" ({i['act_type']})" if i.get("act_type") else ""))
        if i.get("resolution"):
            lines.append(f"   Návrh usnesení: {i['resolution']}")
    return "\n".join(lines)


@app.post("/api/programs")
def save_program(body: dict, db=Depends(get_db)):
    organ, md = body.get("organ"), _d(body.get("date"))
    if organ not in E.PROGRAM_ORGANS or not md:
        raise HTTPException(422, "Zadejte orgán a datum zasedání.")
    seen_ids, seen_titles, items = set(), set(), []
    for it in body.get("items") or []:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        oid = it.get("obligation_id")
        if (oid and oid in seen_ids) or norm(title) in seen_titles:
            continue
        seen_ids.add(oid)
        seen_titles.add(norm(title))
        res = ""
        if oid:
            r = db.execute("SELECT resolution_text, act_type FROM obligations WHERE id=?", (oid,)).fetchone()
            res = r["resolution_text"] if r else ""
        items.append({"obligation_id": oid, "title": title, "act_type": it.get("act_type"), "resolution": res,
                      "category": it.get("category")})
    db.execute("""INSERT INTO programs(organ,meeting_date,covers_until,answers_json,items_json,updated_at) VALUES(?,?,?,?,?,?)
                  ON CONFLICT(organ,meeting_date) DO UPDATE SET covers_until=excluded.covers_until,
                  answers_json=excluded.answers_json, items_json=excluded.items_json, updated_at=excluded.updated_at""",
               (organ, E.iso(md), body.get("covers_until"), json.dumps(body.get("answers") or {}), json.dumps(items),
                datetime.now().isoformat(timespec="seconds")))
    db.commit()
    p = {"organ": organ, "meeting_date": E.iso(md)}
    return {"ok": True, "count": len(items), "text": _prog_text(p, items)}


@app.get("/api/programs")
def get_program(organ: str, date: str, db=Depends(get_db)):
    r = db.execute("SELECT * FROM programs WHERE organ=? AND meeting_date=?", (organ, date)).fetchone()
    if not r:
        return {"saved": False}
    items = json.loads(r["items_json"])
    return {"saved": True, "organ": organ, "meeting_date": date, "answers": json.loads(r["answers_json"] or "{}"),
            "covers_until": r["covers_until"], "items": items, "text": _prog_text(dict(r), items)}


@app.get("/api/import/template.csv")
def template():
    return FileResponse(ROOT / "data" / "import_template.csv", media_type="text/csv", filename="import_template.csv")


@app.post("/api/import/preview")
async def import_preview(file: UploadFile = File(...), zdroj: str = "", verze: str = "", ucinnost_od: str = "",
                         overeno_dne: str = "", vp_potvrzeno: bool = False, db=Depends(get_db)):
    data = await file.read()
    if len(data) > 20_000_000:
        raise HTTPException(413, "Soubor je příliš velký.")
    try:
        opts = {"zdroj": zdroj, "verze": verze, "ucinnost_od": ucinnost_od, "overeno_dne": overeno_dne, "vp_potvrzeno": vp_potvrzeno}
        for k in ("ucinnost_od", "overeno_dne"):
            if opts[k]:
                _d(opts[k], k)
        if any(v for k, v in opts.items() if k != "vp_potvrzeno") and not all(opts[k] for k in ("verze", "ucinnost_od", "overeno_dne")):
            raise HTTPException(422, "Vyplňte verzi, účinnost i datum ověření (nebo žádné z nich).")
        return importer.build_preview(db, file.filename or "import.csv", data, date.today(), opts)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(422, f"Soubor nelze přečíst: {e}")


@app.post("/api/import/commit")
def import_commit(body: dict, db=Depends(get_db)):
    try:
        return importer.commit(db, body.get("token", ""))
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))


@app.get("/api/import/history")
def import_history(db=Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 20")]


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
