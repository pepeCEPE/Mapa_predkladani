"""Výpočet lhůt a plánování řetězce kroků na známá zasedání.

Pojmy:
  * závazná lhůta        - datum z pravidla (kroky mají každý vlastní, nebo žádnou)
  * termín přípravy      - zasedání minus počet dní nutných pro podklady
  * doporučené projednání - POSLEDNÍ bezpečné zasedání, na kterém se celý řetězec ještě stihne
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

ORGANS = {
    "valna_hromada": "Valná hromada",
    "dozorci_rada": "Dozorčí rada",
    "predstavenstvo": "Představenstvo",
    "hios": "HIOS",
}
PROGRAM_ORGANS = ["predstavenstvo", "dozorci_rada", "valna_hromada"]


def parse_date(s):
    if s is None or s == "":
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def iso(d):
    return d.isoformat() if d else None


def cz(d) -> str:
    d = parse_date(d)
    return f"{d.day}. {d.month}. {d.year}" if d else "—"


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    last = calendar.monthrange(y, m)[1]
    d_is_end = d.day == calendar.monthrange(d.year, d.month)[1]
    return date(y, m, last if d_is_end else min(d.day, last))


def fy_end_date(year: int, fy: str = "12-31") -> date:
    m, d = [int(x) for x in fy.split("-")]
    return date(year, m, min(d, calendar.monthrange(year, m)[1]))


def has_deadline(ob) -> bool:
    return ob.get("deadline_kind") in ("fixed", "after_fy_end")


def candidates(ob, ref: date, fy: str = "12-31") -> list[date]:
    """Všechna data lhůty pravidla v okolí referenčního data (seřazená)."""
    kind = ob.get("deadline_kind")
    out = []
    for y in range(ref.year - 2, ref.year + 3):
        if kind == "fixed":
            for part in (ob.get("deadline_dates") or "").split(";"):
                part = part.strip()
                if not part:
                    continue
                m, d = [int(x) for x in part.split("-")]
                try:
                    out.append(date(y, m, d))
                except ValueError:
                    pass
        elif kind == "after_fy_end":
            out.append(add_months(fy_end_date(y, fy), int(ob.get("deadline_months") or 0)))
    return sorted(set(out))


def next_occurrence(ob, ref: date, fy="12-31"):
    for c in candidates(ob, ref, fy):
        if c >= ref:
            return c
    return None


def duty_deadlines(steps: list[dict], ref: date, fy="12-31") -> list[date | None]:
    """Lhůty kroků jedné povinnosti ve stejném cyklu.

    Kotva = poslední krok s lhůtou (první výskyt >= ref); předchozí kroky berou
    nejpozdější výskyt <= kotva, následující nejbližší výskyt >= kotva.
    """
    idx = [i for i, s in enumerate(steps) if has_deadline(s)]
    res: list[date | None] = [None] * len(steps)
    if not idx:
        return res
    a = idx[-1]
    anchor = next_occurrence(steps[a], ref, fy)
    res[a] = anchor
    if anchor is None:
        return res
    for i in idx[:-1]:
        c = [x for x in candidates(steps[i], anchor, fy) if x <= anchor]
        res[i] = c[-1] if c else None
    return res


def plan_chain(steps: list[dict], meetings: dict[str, list[date]], today: date) -> dict:
    """steps: [{organ, prep_days, gap_days, deadline(date|None), label}] v pořadí kroků."""
    n = len(steps)
    if n == 0:
        return {"status": "none", "best": [], "reasons": [], "warnings": []}
    dl_idx = [i for i, s in enumerate(steps) if s.get("deadline")]
    anchor = dl_idx[-1] if dl_idx else None
    hard = set(range(0, (anchor if anchor is not None else 0) + 1))

    raw = []
    for i, s in enumerate(steps):
        ms = [d for d in meetings.get(s["organ"], []) if d >= today]
        if s.get("deadline"):
            ms = [d for d in ms if d <= s["deadline"]]
        raw.append(sorted(ms))

    feasible: list[tuple] = []

    def ok(i, d):
        s = steps[i]
        if s.get("deadline") and d > s["deadline"]:
            return False
        if i == 0 and d - timedelta(days=s.get("prep_days") or 0) < today:
            return False
        return True

    def rec(i, chosen):
        if len(feasible) > 20000:
            return
        if i == n:
            feasible.append(tuple(chosen))
            return
        placed = False
        prev = next((x for x in reversed(chosen) if x is not None), None)
        for d in raw[i]:
            if not ok(i, d):
                continue
            if prev is not None and (d - prev).days < (steps[i].get("gap_days") or 0):
                continue
            placed = True
            chosen.append(d)
            rec(i + 1, chosen)
            chosen.pop()
        if not placed and i not in hard:
            chosen.append(None)       # navazující krok bez zasedání v kalendáři: nepovinný
            rec(i + 1, chosen)
            chosen.pop()

    rec(0, [])

    def key(a):
        if anchor is None:
            return tuple(-(x.toordinal() if x else 10**7) for x in a)
        before = tuple(a[i].toordinal() for i in range(anchor - 1, -1, -1))
        after = tuple(-(a[i].toordinal() if a[i] else 10**7) for i in range(anchor + 1, n))
        return (a[anchor].toordinal(), before, after)

    result = {"status": "ok", "best": None, "previous": None, "reasons": [], "warnings": [],
              "options": [], "anchor": anchor}
    if feasible:
        feasible.sort(key=key, reverse=True)
        best = feasible[0]
        result["best"] = [iso(x) for x in best]
        result["options"] = [sorted({iso(a[i]) for a in feasible if a[i]}) for i in range(n)]
        if anchor is None:
            pass
        else:
            prev = next((a for a in feasible if a[anchor] < best[anchor]), None)
            if prev:
                result["previous"] = [iso(x) for x in prev]
        for i in range(n):
            if best[i] is None:
                result["warnings"].append(
                    f"Navazující krok „{steps[i].get('label') or ORGANS.get(steps[i]['organ'])}“: "
                    f"v kalendáři není zasedání orgánu {ORGANS.get(steps[i]['organ'], steps[i]['organ'])} po předchozím kroku.")
        return result

    # nic nevyhovuje: neúplný kalendář x konflikt
    for i in sorted(hard):
        s = steps[i]
        window_all = [d for d in meetings.get(s["organ"], []) if d >= today and (not s.get("deadline") or d <= s["deadline"])]
        if not window_all:
            until = f" do {cz(s['deadline'])}" if s.get("deadline") else ""
            result["status"] = "incomplete"
            result["reasons"].append(
                f"Kalendář není úplný: nejsou zadána žádná zasedání orgánu {ORGANS.get(s['organ'], s['organ'])}{until}.")
    if result["status"] != "incomplete":
        result["status"] = "conflict"
        result["reasons"] = _explain(steps, raw, anchor if anchor is not None else 0, today)
    return result


def _explain(steps, raw, anchor, today) -> list[str]:
    reasons = []
    for d in reversed(raw[anchor]):
        limit = d
        why = None
        for j in range(anchor - 1, -1, -1):
            gap = steps[j + 1].get("gap_days") or 0
            lim = limit - timedelta(days=gap)
            opts = [x for x in raw[j] if x <= lim]
            if not opts:
                why = (f"Zasedání {ORGANS.get(steps[anchor]['organ'])} {cz(d)} nevyhovuje: nejpozději {cz(lim)} "
                       f"(odstup {gap} dní) není zasedání orgánu {ORGANS.get(steps[j]['organ'])}.")
                break
            limit = opts[-1]
        if why is None:
            prep = steps[0].get("prep_days") or 0
            first = limit
            why = (f"Zasedání {ORGANS.get(steps[anchor]['organ'])} {cz(d)} nevyhovuje: podklady pro "
                   f"{ORGANS.get(steps[0]['organ'])} {cz(first)} by musely být hotové do {cz(first - timedelta(days=prep))}, "
                   f"což je před dnešním datem ({cz(today)}).")
        reasons.append(why)
    if not reasons:
        reasons.append("Žádné zasedání nevyhovuje lhůtě a předstihu.")
    return reasons


def cycle_deadlines(steps, i, D, fy="12-31"):
    """Lhůty všech kroků ve stejném cyklu, když krok i má lhůtu D."""
    res = [None] * len(steps)
    res[i] = D
    for j, s in enumerate(steps):
        if j == i or not has_deadline(s):
            continue
        c = candidates(s, D, fy)
        if j < i:
            c = [x for x in c if x <= D]
            res[j] = c[-1] if c else None
        else:
            c = [x for x in c if x >= D]
            res[j] = c[0] if c else None
    return res
