"""Aplikační logika: kontrola programu, dashboard, kalendář, doporučení."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta

from . import engine as E
from .db import get_setting
from .textutil import norm

CHECKLIST = [
    {"key": "member_change", "label": "Mění se člen orgánu (volba, odvolání, odstoupení)?"},
    {"key": "remuneration", "label": "Mění se odměňování (odměny, bonusy, pohyblivá složka)?"},
    {"key": "office_contract", "label": "Uzavírá se nebo mění smlouva o výkonu funkce?"},
    {"key": "major_transaction", "label": "Připravuje se významná smlouva nebo majetková transakce?"},
    {"key": "outsourcing", "label": "Zavádí se nebo mění outsourcing?"},
    {"key": "internal_regulation", "label": "Mění se vnitřní předpis?"},
    {"key": "conflict_of_interest", "label": "Vznikl střet zájmů?"},
    {"key": "auditor_change", "label": "Mění se auditor?"},
]


def today_of(s=None) -> date:
    return E.parse_date(s) if s else date.today()


def load_obligations(db) -> list[dict]:
    return [dict(r) for r in db.execute("SELECT * FROM obligations ORDER BY duty_code, step_no, id")]


def fy_of(db) -> str:
    return get_setting(db, "fy_end", "12-31")


def meetings_map(db, extra: dict | None = None) -> dict[str, list[date]]:
    m = defaultdict(list)
    for r in db.execute("SELECT organ, date FROM meetings ORDER BY date"):
        m[r["organ"]].append(E.parse_date(r["date"]))
    for o, d in (extra or {}).items():
        if d not in m[o]:
            m[o].append(d)
    return {k: sorted(set(v)) for k, v in m.items()}


def is_confirmed(ob: dict, ref: date) -> bool:
    if ob["status"] != "potvrzeno":
        return False
    ef = E.parse_date(ob.get("effective_from"))
    return not (ef and ef > ref)


def unconfirmed_reason(ob: dict, ref: date) -> str:
    if ob["status"] != "potvrzeno":
        return ob.get("verify_reason") or "Pravidlo čeká na ověření."
    ef = E.parse_date(ob.get("effective_from"))
    if ef and ef > ref:
        return f"Pravidlo je účinné až od {E.cz(ef)}."
    return ""


def groups(obs: list[dict]) -> dict[str, list[dict]]:
    g = defaultdict(list)
    for o in obs:
        g[o["duty_code"]].append(o)
    for v in g.values():
        v.sort(key=lambda x: (x["step_no"], x["id"]))
    return g


def public(ob: dict, ref: date | None = None) -> dict:
    ref = ref or date.today()
    d = dict(ob)
    d["confirmed"] = is_confirmed(ob, ref)
    d["unconfirmed_reason"] = unconfirmed_reason(ob, ref)
    d["organ_label"] = E.ORGANS.get(ob["organ"], ob["organ"])
    return d


def plan_duty(steps: list[dict], ref: date, meetings, today: date, fy: str, deadlines=None) -> dict:
    dls = deadlines if deadlines is not None else E.duty_deadlines(steps, ref, fy)
    chain = [{"organ": s["organ"], "prep_days": s["prep_days"] or 0, "gap_days": s["gap_days"] or 0,
              "deadline": dls[i], "label": s.get("role") or s["act_type"]} for i, s in enumerate(steps)]
    # odstup se vztahuje k předchozímu kroku; první krok ho nemá
    if chain:
        chain[0]["gap_days"] = 0
    p = E.plan_chain(chain, meetings, today)
    p["deadlines"] = [E.iso(x) for x in dls]
    best = p.get("best")
    p["steps"] = [{"id": s["id"], "step_no": s["step_no"], "organ": s["organ"], "organ_label": E.ORGANS.get(s["organ"]),
                   "role": s["role"], "act_type": s["act_type"], "deadline": p["deadlines"][i],
                   "date": best[i] if best else None,
                   "prep_date": E.iso(E.parse_date(best[i]) - timedelta(days=s["prep_days"] or 0)) if best and best[i] else None,
                   "previous_date": p["previous"][i] if p.get("previous") else None}
                  for i, s in enumerate(steps)]
    if p.get("previous"):
        f = E.parse_date(p["previous"][0])
        p["notice_on"] = E.iso(f - timedelta(days=steps[0]["prep_days"] or 0))
    return p


def _cat_rank(c):
    return {"must": 0, "check": 1, "suggest": 2}[c]


def check_program(db, organ: str, mdate: date, covers_until: date | None, answers: dict, today: date) -> dict:
    fy = fy_of(db)
    obs = load_obligations(db)
    gs = groups(obs)
    known = meetings_map(db)
    meetings = meetings_map(db, {organ: mdate})
    org_dates = [d for d in known.get(organ, []) if d > mdate]
    next_meeting = org_dates[0] if org_dates else None
    if covers_until is None:
        covers_until = (next_meeting - timedelta(days=1)) if next_meeting else mdate + timedelta(days=90)
    prog = db.execute("SELECT * FROM programs WHERE organ=? AND meeting_date=?", (organ, E.iso(mdate))).fetchone()
    saved = None
    if prog:
        saved = {i["obligation_id"] for i in json.loads(prog["items_json"] or "[]") if i.get("obligation_id")}
        saved_titles = {norm(i["title"]) for i in json.loads(prog["items_json"] or "[]")}

    def in_prog(ob):
        if saved is None:
            return "neznámý"
        return "ano" if ob["id"] in saved or norm(ob.get("agenda_title") or ob["subject"]) in saved_titles else "ne"

    items: dict[int, dict] = {}
    follow = []
    warnings = []

    def add(ob, cat, reason, plan=None, warn=None, deadline=None, latest=None):
        confirmed = is_confirmed(ob, mdate)
        if not confirmed and cat == "must":
            cat = "check"
            reason = f"K ověření – {unconfirmed_reason(ob, mdate)} (původně: {reason})"
        it = items.get(ob["id"])
        if it is None:
            it = {"obligation_id": ob["id"], "duty_code": ob["duty_code"], "step_no": ob["step_no"],
                  "title": ob.get("agenda_title") or ob["subject"], "subject": ob["subject"], "organ": ob["organ"],
                  "act_type": ob["act_type"], "category": cat, "reasons": [], "warnings": [],
                  "confirmed": confirmed, "unconfirmed_reason": unconfirmed_reason(ob, mdate),
                  "deadline": E.iso(deadline), "latest_safe": E.iso(latest), "in_program": in_prog(ob),
                  "source": f"{ob.get('source_name') or ''} {ob.get('source_ref') or ''}".strip(),
                  "chain": []}
            items[ob["id"]] = it
        if _cat_rank(cat) < _cat_rank(it["category"]):
            it["category"] = cat
        if reason not in it["reasons"]:
            it["reasons"].append(reason)
        if warn:
            it["warnings"].extend(w for w in (warn if isinstance(warn, list) else [warn]) if w not in it["warnings"])
        if plan and not it["chain"]:
            it["chain"] = [{"organ_label": s["organ_label"], "role": s["role"], "act_type": s["act_type"],
                            "date": s["date"], "current": s["id"] == ob["id"]} for s in plan["steps"]]

    for duty, steps in gs.items():
        organs_in = [s for s in steps if s["organ"] == organ]
        if not organs_in:
            continue
        kind = steps[0]["kind"]
        if kind == "event":
            plan = None
            for s in organs_in:
                keys = [k for k in s["trigger_key"].split(";") if k]
                ans = {answers.get(k) for k in keys}
                if "ano" in ans:
                    if plan is None:
                        plan = plan_duty(steps, mdate, meetings, today, fy, [None] * len(steps))
                    why = "Událost nastala (odpověď Ano v situačním checklistu)."
                    add(s, "must", why, plan)
                    items[s["id"]]["conditions"] = s.get("conditions")
                elif "nevim" in ans:
                    add(s, "check", "Použitelnost není jistá (odpověď Nevím v situačním checklistu).")
            if any(answers.get(k) == "ano" for s in steps for k in s["trigger_key"].split(";") if k):
                plan = plan or plan_duty(steps, mdate, meetings, today, fy, [None] * len(steps))
                for st in plan["steps"]:
                    if st["organ"] != organ:
                        follow.append({"duty_code": duty, "subject": steps[0]["subject"], "organ_label": st["organ_label"],
                                       "role": st["role"], "act_type": st["act_type"], "planned": st["date"]})
            continue
        # periodická povinnost
        dls = E.duty_deadlines(steps, mdate, fy)
        plan = plan_duty(steps, mdate, meetings, today, fy, dls)
        for i, s in enumerate(steps):
            if s["organ"] != organ:
                continue
            D = dls[i]
            st = plan["steps"][i]
            if not E.has_deadline(steps[i]) and not any(E.has_deadline(x) for x in steps):
                add(s, "check", "Lhůta není v pravidle určena – prověřte, zda a kdy bod zařadit.", plan)
                continue
            if plan["status"] == "ok" and plan["best"][i]:
                best = E.parse_date(plan["best"][i])
                opts = [E.parse_date(x) for x in plan["options"][i]]
                if best == mdate:
                    why = f"Poslední bezpečné zasedání pro lhůtu {E.cz(D)}" if D else "Poslední bezpečné zasedání"
                    nxt = f"; další známé zasedání ({E.cz(next_meeting)}) už je pozdě." if next_meeting and (D is None or next_meeting > best) else "."
                    cat = "must" if s["applicability"] == "always" else "check"
                    if cat == "check":
                        why = "Platí jen za podmínek – " + (s["conditions"] or "ověřte použitelnost") + ". " + why
                    add(s, cat, why + nxt, plan, plan["warnings"], D, best)
                elif best > mdate and mdate in opts and (D is None or D <= covers_until):
                    cat = "suggest"
                    add(s, cat, f"Lze projednat s předstihem; poslední bezpečné zasedání je {E.cz(best)} (lhůta {E.cz(D)}).",
                        plan, plan["warnings"], D, best)
            else:
                if D is None or D > covers_until:
                    continue
                last_ok = [d for d in meetings.get(organ, []) if d <= D]
                if last_ok and last_ok[-1] == mdate and mdate >= today:
                    add(s, "must" if s["applicability"] == "always" else "check",
                        f"Poslední zasedání před lhůtou {E.cz(D)}, ale řetězec kroků nelze bezpečně naplánovat.",
                        plan, plan["reasons"], D, mdate)
                else:
                    add(s, "check", f"Lhůta {E.cz(D)} spadá do sledovaného období, ale doporučení nelze vypočítat.",
                        plan, plan["reasons"], D, None)
                    warnings.append(f"{s['subject']}: " + " ".join(plan["reasons"]))

    # sloučení stejných bodů programu (stejný název) – bod se nepřidává dvakrát
    merged: dict[str, dict] = {}
    for it in sorted(items.values(), key=lambda x: (_cat_rank(x["category"]), x["title"])):
        k = norm(it["title"])
        if k in merged:
            m = merged[k]
            m["reasons"] += [r for r in it["reasons"] if r not in m["reasons"]]
            m["merged_obligation_ids"] = m.get("merged_obligation_ids", []) + [it["obligation_id"]]
        else:
            merged[k] = it
    out = list(merged.values())
    res = {"must": [], "check": [], "suggest": []}
    for it in out:
        res[it["category"]].append(it)
    return {"organ": organ, "organ_label": E.ORGANS[organ], "meeting_date": E.iso(mdate),
            "covers_until": E.iso(covers_until), "next_meeting": E.iso(next_meeting),
            "saved_program": bool(prog), "today": E.iso(today), **res, "follow_ups": follow,
            "warnings": warnings, "counts": {k: len(v) for k, v in res.items()}}


def dashboard(db, today: date) -> dict:
    fy = fy_of(db)
    meetings = meetings_map(db)
    nxt = []
    for organ in E.PROGRAM_ORGANS:
        ds = [d for d in meetings.get(organ, []) if d >= today]
        if not ds:
            nxt.append({"organ": organ, "organ_label": E.ORGANS[organ], "date": None, "must": None})
            continue
        r = check_program(db, organ, ds[0], None, {}, today)
        nxt.append({"organ": organ, "organ_label": E.ORGANS[organ], "date": E.iso(ds[0]), "must": r["counts"]["must"],
                    "check": r["counts"]["check"], "suggest": r["counts"]["suggest"]})
    cal = calendar_items(db, today, today, today + timedelta(days=90))
    return {"today": E.iso(today), "next_meetings": nxt,
            "upcoming": [i for i in cal if i["confirmed"]], "upcoming_unverified": [i for i in cal if not i["confirmed"]]}


def calendar_items(db, today: date, start: date, end: date) -> list[dict]:
    """Periodické povinnosti, jejichž závazná lhůta kroku leží v [start, end]."""
    fy = fy_of(db)
    meetings = meetings_map(db)
    gs = groups(load_obligations(db))
    out = []
    for duty, steps in gs.items():
        if steps[0]["kind"] != "periodic":
            continue
        for i, s in enumerate(steps):
            if not E.has_deadline(s):
                continue
            for D in E.candidates(s, start, fy):
                if not (start <= D <= end):
                    continue
                dls = E.cycle_deadlines(steps, i, D, fy)
                plan = plan_duty(steps, D, meetings, today, fy, dls) if D >= today else {"status": "past", "steps": [], "reasons": [], "warnings": []}
                st = plan["steps"][i] if plan.get("steps") else {}
                conf = is_confirmed(s, D)
                out.append({"obligation_id": s["id"], "duty_code": duty, "subject": s["subject"], "organ": s["organ"],
                            "organ_label": E.ORGANS.get(s["organ"]), "act_type": s["act_type"], "step_no": s["step_no"],
                            "deadline": E.iso(D), "prep_date": st.get("prep_date"), "recommended": st.get("date"),
                            "previous": st.get("previous_date"), "notice_on": plan.get("notice_on"),
                            "plan_status": plan["status"], "reasons": plan.get("reasons", []),
                            "warnings": plan.get("warnings", []), "confirmed": conf,
                            "unconfirmed_reason": unconfirmed_reason(s, D), "is_demo": s["is_demo"],
                            "chain": [{"organ_label": x["organ_label"], "role": x["role"], "date": x["date"]} for x in plan.get("steps", [])]})
    out.sort(key=lambda x: (x["deadline"], x["subject"]))
    return out


def recommend(db, duty_code: str, deadline: date | None, today: date) -> dict:
    """Doporučení pro řetězec kroků; u povinnosti vyvolané událostí lze zadat vlastní lhůtu posledního kroku."""
    fy = fy_of(db)
    steps = groups(load_obligations(db)).get(duty_code)
    if not steps:
        raise KeyError(duty_code)
    if deadline:
        dls = [None] * len(steps)
        dls[-1] = deadline
    elif any(E.has_deadline(s) for s in steps):
        dls = E.duty_deadlines(steps, today, fy)
    else:
        dls = [None] * len(steps)
    plan = plan_duty(steps, deadline or today, meetings_map(db), today, fy, dls)
    plan["duty_code"] = duty_code
    plan["subject"] = steps[0]["subject"]
    plan["confirmed"] = all(is_confirmed(s, today) for s in steps)
    return plan
