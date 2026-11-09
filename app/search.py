from __future__ import annotations

from .textutil import norm, synonym_terms, word_match

FIELD_W = [("subject", 5), ("keywords", 4), ("agenda_title", 3), ("documents", 1), ("conditions", 1),
           ("resolution_text", 1), ("follow_up", 1), ("area", 1.5), ("source_ref", 0.5), ("act_type", 0.5), ("role", 1)]


def _hay(ob):
    return {f: norm(ob.get(f)) for f, _ in FIELD_W}


def _term_score(term: str, hay: dict) -> float:
    best = 0.0
    tw = term.split()
    for f, w in FIELD_W:
        h = hay[f]
        if not h:
            continue
        hw = h.split()
        if len(tw) == 1:
            ok = any(word_match(tw[0], x) for x in hw)
        else:
            ok = term in h
        if ok:
            best = max(best, w)
    return best


def search(obligations: list[dict], q: str) -> list[dict]:
    """Vrátí [{duty_code, score, matched:[id], via_synonym:bool}] seřazené podle shody."""
    qn = norm(q)
    toks = qn.split()
    if not toks:
        return []
    syn = synonym_terms(q)
    results: dict[str, dict] = {}
    for ob in obligations:
        hay = _hay(ob)
        covered, score, via = set(), 0.0, False
        for t in toks:
            s = _term_score(t, hay)
            if s:
                covered.add(t)
                score += s
        for term, cov in syn:
            s = _term_score(term, hay)
            if s:
                new = set(cov) - covered
                covered |= set(cov)
                score += s * 0.6 + (0.5 if new else 0)
                via = via or bool(new)
        if len(covered) == len(set(toks)) and score > 0:
            g = results.setdefault(ob["duty_code"], {"duty_code": ob["duty_code"], "score": 0, "matched": [], "via_synonym": False})
            g["score"] = max(g["score"], score)
            g["matched"].append(ob["id"])
            g["via_synonym"] = g["via_synonym"] or via
    return sorted(results.values(), key=lambda g: -g["score"])
