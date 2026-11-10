"""Import mapy z XLSX/CSV: náhled, kontrola řádků, duplicity, idempotentní uložení."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import secrets
from datetime import date, datetime

from .engine import ORGANS, parse_date
from .textutil import norm

NATIVE_FIELDS = ["kod", "kod_povinnosti", "krok", "role", "predmet", "organ", "ukon", "oblast", "typ",
                 "pouzitelnost", "podminky", "vyjimky", "navaznosti", "lhuta_typ", "lhuta_data", "lhuta_mesicu",
                 "lhuta_text", "priprava_dnu", "odstup_dnu", "podklady", "bod_programu", "navrh_usneseni",
                 "spoustec", "klicova_slova", "zdroj", "clanek", "verze", "ucinnost_od", "overeno_dne", "stav",
                 "duvod_k_overeni"]
ACTS = ["informování", "schválení", "projednání", "rozhodnutí", "vyhodnocení", "konání", "vzetí na vědomí", "vyjádření",
        "předložení"]
TRIGGERS = ["member_change", "remuneration", "office_contract", "major_transaction", "outsourcing",
            "internal_regulation", "conflict_of_interest", "auditor_change"]
ORGAN_ALIASES = {"valna hromada": "valna_hromada", "vh": "valna_hromada", "dozorci rada": "dozorci_rada",
                 "dr": "dozorci_rada", "predstavenstvo": "predstavenstvo", "pr": "predstavenstvo",
                 "hios": "hios"}
ECRU_HEADERS = {"cislo povinnosti", "oznaceni", "druh", "zpusob vyrizeni", "vyskyt", "lhuta", "organ"}

DB_FIELDS = ["code", "duty_code", "step_no", "role", "subject", "organ", "act_type", "area", "kind",
             "applicability", "conditions", "exceptions", "follow_up", "deadline_kind", "deadline_dates",
             "deadline_months", "deadline_text", "prep_days", "gap_days", "documents", "agenda_title",
             "resolution_text", "trigger_key", "keywords", "status", "verify_reason", "source_name",
             "source_ref", "source_version", "effective_from", "verified_on", "responsible", "submitter", "nature",
             "approvers"]


def _s(v):
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    return str(v).strip()


def _detect(rows):
    for idx, (ln, r) in enumerate(rows[:10]):
        hn = {norm(c) for c in r if c}
        if ECRU_HEADERS <= hn:
            return {"headers": [norm(c) for c in r], "rows": rows[idx + 1:], "layout": "ecru"}
        nat = {norm(f.replace("_", " ")) for f in NATIVE_FIELDS}
        if len(hn & nat) >= 6:
            return {"headers": [norm(c) for c in r], "rows": rows[idx + 1:], "layout": "native"}
    return None


def _numbers(scope: str) -> list[int]:
    """„Č. 58 – …“, „Č. 63 a 89“, „Č. 85, 91, 155–156“ -> čísla povinností."""
    sc = scope.strip()
    if not re.match(r"[ČC]\.", sc):
        return []
    sc = re.sub(r"^[ČC]\.\s*", "", sc).split(" – ")[0]
    out = []
    for m in re.finditer(r"(\d+)\s*[–-]\s*(\d+)|(\d+)", sc):
        if m.group(3):
            out.append(int(m.group(3)))
        else:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
    return out


def _read_findings(rows) -> list[dict]:
    for idx, (ln, r) in enumerate(rows[:8]):
        hn = [norm(c) for c in r]
        if "zjisteni" in hn and any(x.startswith("existujici polozka") for x in hn):
            out = []
            ci = {name: hn.index(name) for name in hn if name}
            iz = hn.index("zjisteni")
            ie = next(i for i, x in enumerate(hn) if x.startswith("existujici polozka"))
            for _, row in rows[idx + 1:]:
                if len(row) > iz and row[iz]:
                    out.append({"area": row[0], "scope": row[ie], "text": row[iz], "numbers": _numbers(row[ie])})
            return out
    return []


def read_tables(filename: str, data: bytes):
    """Vrátí ([{sheet, index, headers, rows, layout}], zjištění z kontroly mapy)."""
    sheets = []
    if filename.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        for ws in wb.worksheets:
            sheets.append((ws.title, [(i, [_s(c) for c in r]) for i, r in enumerate(ws.iter_rows(values_only=True), start=1)]))
    else:
        text = data.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        sheets.append(("csv", [(i, [c.strip() for c in r]) for i, r in enumerate(csv.reader(io.StringIO(text), dialect), start=1)]))
    tables, findings = [], []
    for idx, (name, rows) in enumerate(sheets):
        t = _detect(rows)
        if t:
            tables.append({"sheet": name, "index": idx, **t})
        else:
            findings += _read_findings(rows)
    if not tables:
        raise ValueError("Nepodařilo se rozpoznat hlavičku souboru (očekávám šablonu nebo sloupce mapy předkládání).")
    return tables, findings


def _classify_fill(rgb: str | None) -> str | None:
    """Barva buňky -> význam podle poznámek pod tabulkou mapy."""
    if not rgb or len(rgb) < 6:
        return None
    import colorsys
    r, g, b = (int(rgb[-6:][i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    if v > 0.93 and sat < 0.12:
        return None                  # téměř bílá / krémová = bez významu
    if sat < 0.08:
        return "grey"
    if 175 <= h <= 235:
        return "blue"
    if 15 <= h < 36:
        return "orange"
    if 36 <= h <= 65:
        return "yellow"
    if h < 15 or h > 340:
        return "red"
    return None


def read_meta(filename: str, data: bytes, col: int, sheet: int = 0) -> dict[int, dict]:
    """Řádek -> {fill, comment} pro buňku zdroje (jen XLSX)."""
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        return {}
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(data)).worksheets[sheet]
    out = {}
    for row in ws.iter_rows(min_row=1):
        c = row[col] if col < len(row) else None
        if c is None:
            continue
        rgb = c.fill.fgColor.rgb if c.fill and c.fill.fill_type and isinstance(c.fill.fgColor.rgb, str) else None
        out[c.row] = {"fill": _classify_fill(rgb), "comment": (c.comment.text.strip() if c.comment else "")}
    return out


def _organ(v):
    n = norm(re.sub(r"\(.*?\)", " ", v or "", flags=re.S))
    return ORGAN_ALIASES.get(n)


def _split_dates(text):
    out = []
    for m in re.finditer(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.", text or ""):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            out.append(f"{mo}-{d}")
    return ";".join(dict.fromkeys(out))


MONTHS = {"ledna": 1, "unora": 2, "brezna": 3, "dubna": 4, "kvetna": 5, "cervna": 6, "cervence": 7, "srpna": 8,
          "zari": 9, "rijna": 10, "listopadu": 11, "prosince": 12}


def _month_end(text):
    """„do konce března“ -> 3-31."""
    m = re.search(r"do konce (\w+)", norm(text))
    if m and m.group(1) in MONTHS:
        mo = MONTHS[m.group(1)]
        return f"{mo}-{[31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]}"
    return ""


VP_RE = re.compile(r"^(VP_\d+(?:_\d+)?)\s+(.+?)\s*\(účinnost od\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\)\s*,\s*(.+)$", re.S)


def _parse_vp(src: str):
    m = VP_RE.match((src or "").strip())
    if not m:
        return None
    code, name, d, mo, y, art = m.groups()
    return {"zdroj": f"{code} {name}", "clanek": art.strip(), "ucinnost_od": f"{int(y):04d}-{int(mo):02d}-{int(d):02d}",
            "verze": f"{code}, účinnost od {int(d)}. {int(mo)}. {y}"}


def _act(v):
    n = norm(v)
    for key, val in (("schval", "schválení"), ("projedn", "projednání"), ("rozhod", "rozhodnutí"),
                     ("vyhodnoc", "vyhodnocení"), ("informov", "informování"), ("vedomi", "vzetí na vědomí"), ("vyjad", "vyjádření"),
                     ("predlo", "předložení"), ("kon", "konání")):
        if key in n:
            return val
    return _s(v)


def _from_ecru(h: list[str], r: list[str]) -> dict:
    g = lambda name: _s(r[h.index(name)]) if name in h and h.index(name) < len(r) else ""
    num = g("cislo povinnosti")
    occ, lhuta = g("vyskyt"), g("lhuta")
    ev = bool(re.search(r"ad hoc|v pripade|podle potreby|pri |po zasedani|na zadost|kdykoli|jednorazove|po provedeni|pred rozhodnutim",
                        norm(occ + " " + lhuta))) or norm(g("druh")).startswith("mimoradn")
    dates = _split_dates(lhuta) or _month_end(lhuta)
    months = re.search(r"(\d+)\s*m[eě]s[ií]c", lhuta)
    kind_dl, dmonths = "none", None
    if re.search(r"(u|s)konceni ucetniho obdobi|konce ucetniho obdobi", norm(lhuta)):
        if months:
            kind_dl, dmonths = "after_fy_end", int(months.group(1))
    elif dates and not ev:
        kind_dl = "fixed"
    elif dates:
        kind_dl = "fixed"
    organ_raw = g("organ")
    return {
        "kod": f"MAPA-{num}", "kod_povinnosti": f"MAPA-{num}", "krok": "1", "role": "",
        "predmet": g("oznaceni"), "organ": re.split(r"[\n/;]", re.sub(r"\(.*?\)", " ", organ_raw, flags=re.S))[0].strip(), "_organ_raw": re.sub(r"\(.*?\)", " ", organ_raw, flags=re.S),
        "ukon": _act(g("zpusob vyrizeni")), "oblast": g("proces"), "typ": "udalost" if ev else "periodicka",
        "pouzitelnost": "", "podminky": "", "vyjimky": "", "navaznosti": g("souvisi s cislem povinnosti"),
        "lhuta_typ": kind_dl, "lhuta_data": dates if kind_dl == "fixed" else "", "lhuta_mesicu": dmonths or "",
        "lhuta_text": " | ".join(x for x in (occ, lhuta) if x),
        "priprava_dnu": "", "odstup_dnu": "", "podklady": g("druh"), "bod_programu": g("oznaceni"),
        "navrh_usneseni": "", "spoustec": "", "klicova_slova": "",
        "zdroj": "Mapa předkládání (import)", "clanek": g("zdroje povinnosti"), "verze": "", "ucinnost_od": "",
        "overeno_dne": "", "stav": "", "duvod_k_overeni": "",
        "_ecru": True, "_obsah": g("obsah povinnosti") + " " + g("blizsi urceni obsahu"),
        "_num": int(num) if str(num).isdigit() else None, "_resp": g("odpovedny subjekt"),
        "_subm": g("povinne predkladajici osoba"), "_nature": g("povaha povinnosti"),
        "_appr": "; ".join(x for x in (g("schvalovatel 1"), g("schvalovatel 2")) if x and norm(x) != "neni"),
    }


def _rec(h, r):
    g = lambda name: _s(r[h.index(name)]) if name in h and h.index(name) < len(r) else ""
    return {f: g(norm(f.replace("_", " "))) for f in NATIVE_FIELDS}


def normalize_record(raw: dict, today: date, opts: dict | None = None) -> tuple[dict | None, list[str], list[str]]:
    errors, warnings = [], []
    subject = raw["predmet"]
    organ = _organ(raw["organ"])
    if not subject:
        errors.append("Chybí předmět povinnosti.")
    if not raw["organ"]:
        errors.append("Chybí orgán.")
    elif not organ:
        errors.append(f"Neznámý orgán „{raw['organ']}“ (povoleno: valná hromada, dozorčí rada, představenstvo, HIOS).")
    if raw.get("_organ_raw") and re.search(r"[\n/]", raw["_organ_raw"]):
        warnings.append("Řádek uvádí více orgánů; převzat byl první, ostatní kroky doplňte ručně.")
    if not raw["ukon"]:
        errors.append("Chybí typ úkonu.")
    elif raw["ukon"] not in ACTS and not raw.get("_ecru"):
        warnings.append(f"Neobvyklý typ úkonu „{raw['ukon']}“.")
    typ = norm(raw["typ"])
    kind = "periodic" if typ.startswith("period") else "event" if typ.startswith(("udal", "event", "ad hoc", "vyvol")) else None
    if kind is None:
        errors.append("Typ povinnosti musí být „periodická“ nebo „událost“.")
    step = raw["krok"] or "1"
    if not re.fullmatch(r"\d+", step):
        errors.append(f"Krok musí být celé číslo, je „{step}“.")
        step = "1"

    def num(name, default):
        v = raw[name]
        if v == "":
            return default
        try:
            n = int(float(v))
            if n < 0:
                raise ValueError
            return n
        except ValueError:
            errors.append(f"Pole {name} musí být nezáporné číslo, je „{v}“.")
            return default

    prep, gap = num("priprava_dnu", 14), num("odstup_dnu", 0)
    dk = norm(raw["lhuta_typ"]) or "none"
    dk = {"pevne datum": "fixed", "fixed": "fixed", "po konci obdobi": "after_fy_end", "after fy end": "after_fy_end",
          "none": "none", "bez lhuty": "none", "": "none"}.get(dk, dk)
    if dk not in ("fixed", "after_fy_end", "none"):
        errors.append(f"Neznámý typ lhůty „{raw['lhuta_typ']}“ (fixed / after_fy_end / none).")
        dk = "none"
    dates = raw["lhuta_data"].replace(",", ";")
    months = None
    if dk == "fixed":
        parts = [p.strip() for p in dates.split(";") if p.strip()]
        clean = []
        for p in parts:
            m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", p)
            if not m or not (1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31):
                errors.append(f"Neplatné datum lhůty „{p}“ (formát měsíc-den, např. 6-30).")
            else:
                clean.append(p)
        if not clean and not parts:
            errors.append("Lhůta „fixed“ vyžaduje datum (např. 6-30).")
        dates = ";".join(clean)
    elif dk == "after_fy_end":
        months = num("lhuta_mesicu", None)
        if months is None:
            errors.append("Lhůta „after_fy_end“ vyžaduje počet měsíců.")
    else:
        dates = ""
    for f in ("ucinnost_od", "overeno_dne"):
        if raw[f]:
            try:
                parse_date(raw[f])
            except ValueError:
                errors.append(f"Neplatné datum v poli {f}: „{raw[f]}“ (formát RRRR-MM-DD).")
    if raw["overeno_dne"] and not errors:
        try:
            if parse_date(raw["overeno_dne"]) > today:
                warnings.append("Datum ověření je v budoucnosti.")
        except ValueError:
            pass
    trig = [t.strip() for t in re.split(r"[;,]", raw["spoustec"]) if t.strip()]
    for t in trig:
        if t not in TRIGGERS:
            warnings.append(f"Neznámý spouštěč „{t}“ (známé: {', '.join(TRIGGERS)}).")
    if errors:
        return None, errors, warnings

    # stav: potvrzeno jen s kompletním zdrojem
    reasons = []
    wanted = norm(raw["stav"])
    if wanted.startswith("k overeni") and raw["duvod_k_overeni"]:
        reasons.append(raw["duvod_k_overeni"])
    elif wanted.startswith("k overeni"):
        reasons.append("Označeno jako K ověření bez uvedeného důvodu.")
    missing = [lbl for lbl, v in (("zdroj", raw["zdroj"]), ("článek / bod", raw["clanek"]), ("verze", raw["verze"]),
                                  ("účinnost", raw["ucinnost_od"]), ("datum ověření", raw["overeno_dne"])) if not v]
    if missing and not raw.get("_ecru"):
        reasons.append("Chybí podklad: " + ", ".join(missing) + ".")
    if raw.get("_ecru"):
        opts = opts or {}
        n = norm(raw["clanek"])
        bad_src = not raw["clanek"] or "nečitelné" in raw["clanek"].lower() or "neni povinne" in n
        meta = raw.get("_meta") or {}
        fill, comment = meta.get("fill"), meta.get("comment") or ""
        notes = []
        if bad_src:
            reasons.append("Zdroj povinnosti chybí, je nečitelný nebo uvádí „není povinné schvalovat“.")
        if "nečitelné" in (raw["predmet"] + raw.get("_obsah", "")).lower():
            reasons.append("V podkladu je nečitelný text.")
            bad_src = True
        if fill == "orange":
            reasons.append("Zdroj nedohledán (oranžově v podkladu: odkaz na stanovy vymazán).")
            bad_src = True
        elif fill == "grey":
            reasons.append("Zdroj tvořil jen vnitřní předpis nebo ve stanovách není – podle podkladu schvalování tímto orgánem není povinné (šedě).")
            bad_src = True
        elif fill == "red":
            reasons.append("Údaj je v podkladu označen jako špatně čitelný nebo nejistý (červeně).")
            bad_src = True
        elif fill == "yellow":
            warnings.append("Žlutě v podkladu: zdroj, lhůta nebo výskyt opraveny podle stanov / zákona.")
        elif fill == "blue":
            warnings.append("Modře v podkladu: povinnost doplněna z ZOK nebo stanov, v původní tabulce chyběla.")
        if comment:
            notes.append("Komentář v podkladu: " + comment.replace("\n", " "))
        fl = raw.get("_findings") or []
        if fl:
            txt = " ".join(fl)
            if re.search(r"overit|neuvadi", norm(txt)):
                reasons.append("Zjištění kontroly mapy: " + txt)
            else:
                notes.append("Zjištění kontroly mapy: " + txt)
        vp = _parse_vp(raw["clanek"])
        full = all(opts.get(k) for k in ("verze", "ucinnost_od", "overeno_dne"))
        if vp:
            raw.update(vp)
            if opts.get("vp_potvrzeno") and opts.get("overeno_dne") and not bad_src:
                raw["overeno_dne"] = opts["overeno_dne"]
                warnings.append("Vnitřní předpis: použitelnost po změně názvu na ECRU potvrzena uživatelem při importu.")
            else:
                reasons.append("Zdroj je vnitřní předpis ve znění označeném Proton; použitelnost po změně názvu na ECRU "
                               "a schválení musí potvrdit Compliance nebo právník.")
        elif full and not bad_src:
            raw["zdroj"] = opts.get("zdroj") or raw["zdroj"]
            raw["verze"], raw["ucinnost_od"], raw["overeno_dne"] = opts["verze"], opts["ucinnost_od"], opts["overeno_dne"]
            warnings.append("Verze, účinnost a datum ověření doplněny při importu uživatelem.")
        else:
            reasons.append("Neschválený podklad: chybí verze, účinnost a datum ověření.")
        raw["_notes"] = notes
    if wanted and not wanted.startswith(("k overeni", "potvrzeno")):
        warnings.append(f"Neznámý stav „{raw['stav']}“, bude vyhodnocen podle úplnosti podkladu.")
    status = "k_overeni" if reasons else "potvrzeno"
    code = raw["kod"]
    duty = raw["kod_povinnosti"] or code
    key_src = "|".join([norm(duty), step, norm(subject), organ or "", norm(raw["ukon"])])
    if not code:
        code = "AUTO-" + hashlib.sha1(key_src.encode()).hexdigest()[:10]
        duty = raw["kod_povinnosti"] or code
    applic = "conditional" if norm(raw["pouzitelnost"]).startswith(("podm", "cond")) or (raw["podminky"] and norm(raw["pouzitelnost"]) != "vzdy") else "always"
    rec = {
        "code": code, "duty_code": duty, "step_no": int(step), "role": raw["role"], "subject": subject,
        "organ": organ, "act_type": raw["ukon"], "area": raw["oblast"], "kind": kind, "applicability": applic,
        "conditions": raw["podminky"], "exceptions": (raw["vyjimky"] + "\n" + " ".join(raw.get("_notes", []))).strip() if not reasons else raw["vyjimky"], "follow_up": raw["navaznosti"],
        "deadline_kind": dk, "deadline_dates": dates, "deadline_months": months,
        "deadline_text": raw["lhuta_text"], "prep_days": prep, "gap_days": gap, "documents": raw["podklady"],
        "agenda_title": raw["bod_programu"] or subject, "resolution_text": raw["navrh_usneseni"],
        "trigger_key": ";".join(trig), "keywords": raw["klicova_slova"], "status": status,
        "verify_reason": " ".join(reasons + raw.get("_notes", [])) if reasons else "", "source_name": raw["zdroj"], "source_ref": raw["clanek"],
        "source_version": raw["verze"], "effective_from": raw["ucinnost_od"] or None,
        "verified_on": raw["overeno_dne"] or None, "responsible": raw.get("_resp", ""), "submitter": raw.get("_subm", ""),
        "nature": raw.get("_nature", ""), "approvers": raw.get("_appr", ""),
    }
    return rec, errors, warnings


def content_hash(rec: dict) -> str:
    return hashlib.sha256(json.dumps({k: rec.get(k) for k in DB_FIELDS}, sort_keys=True, default=str).encode()).hexdigest()


def build_preview(db, filename: str, data: bytes, today: date, opts: dict | None = None) -> dict:
    sha = hashlib.sha256(data).hexdigest()
    tables, findings = read_tables(filename, data)
    layout = tables[0]["layout"]
    fmap: dict[int, list[str]] = {}
    for f in findings:
        for n in f["numbers"]:
            fmap.setdefault(n, []).append(f"{f['area']}: {f['text']}")
    entries = []
    for tb in tables:
        h, lay = tb["headers"], tb["layout"]
        mt = read_meta(filename, data, h.index("zdroje povinnosti"), tb["index"]) if lay == "ecru" and "zdroje povinnosti" in h else {}
        for ln, r in tb["rows"]:
            entries.append((h, lay, mt, ln, r, tb["sheet"] if len(tables) > 1 and tb is not tables[0] else None))
    out, seen_codes, seen_sig = [], {}, {}
    existing = {r["code"]: r["content_hash"] for r in db.execute("SELECT code, content_hash FROM obligations")}
    for headers, lay, meta, ln0, r, sheet in entries:
        ln = f"{sheet}!{ln0}" if sheet else ln0
        if not any(c for c in r):
            continue
        raw = _from_ecru(headers, r) if lay == "ecru" else _rec(headers, r)
        if lay == "ecru" and not raw["predmet"] and not raw["organ"]:
            continue  # poznámky pod tabulkou
        if lay == "ecru":
            raw["_meta"] = meta.get(ln0, {})
            raw["_findings"] = fmap.get(raw.get("_num"), [])
        rec, errs, warns = normalize_record(raw, today, opts)
        item = {"line": ln, "record": rec, "errors": errs, "warnings": warns, "action": "error" if errs else "new",
                "code": (rec or {}).get("code") or raw["kod"], "subject": raw["predmet"], "organ": raw["organ"]}
        if rec:
            rec_hash = content_hash(rec)
            item["hash"] = rec_hash
            if rec["code"] in seen_codes:
                item["action"] = "duplicate"
                item["warnings"].append(f"Duplicitní kód {rec['code']} (řádek {seen_codes[rec['code']]}); řádek se přeskočí.")
            else:
                seen_codes[rec["code"]] = ln
                if rec["code"] in existing:
                    item["action"] = "unchanged" if existing[rec["code"]] == rec_hash else "update"
                sig = (norm(rec["subject"]), rec["organ"], norm(rec["act_type"]))
                if sig in seen_sig:
                    prev = seen_sig[sig]
                    if prev["rec"]["deadline_text"] != rec["deadline_text"] or prev["rec"]["source_ref"] != rec["source_ref"]:
                        item["warnings"].append(f"Možný rozpor s řádkem {prev['line']}: stejný předmět, orgán a úkon, ale jiná lhůta nebo zdroj.")
                        item["conflict_with"] = prev["line"]
                    else:
                        item["warnings"].append(f"Možná duplicita řádku {prev['line']} (stejný předmět, orgán a úkon).")
                else:
                    seen_sig[sig] = {"line": ln, "rec": rec}
        out.append(item)
    # rozpory -> oba řádky K ověření
    by_line = {i["line"]: i for i in out}
    for i in out:
        c = i.get("conflict_with")
        if c and i["record"]:
            for tgt, other in ((i, c), (by_line[c], i["line"])):
                if tgt["record"]:
                    tgt["record"]["status"] = "k_overeni"
                    tgt["record"]["verify_reason"] = (tgt["record"]["verify_reason"] + f" Rozporný podklad (řádek {other}).").strip()
                    tgt["hash"] = content_hash(tgt["record"])
    for i in out:
        if i["record"] and i["action"] in ("new", "update", "unchanged") and i["code"] in existing:
            i["action"] = "unchanged" if existing[i["code"]] == i["hash"] else "update"
    already = db.execute("SELECT id, imported_at FROM imports WHERE sha256=?", (sha,)).fetchone()
    summary = {k: sum(1 for i in out if i["action"] == k) for k in ("new", "update", "unchanged", "error", "duplicate")}
    summary["k_overeni"] = sum(1 for i in out if i["record"] and i["record"]["status"] == "k_overeni" and i["action"] != "duplicate")
    token = secrets.token_hex(12)
    payload = {"filename": filename, "sha256": sha, "items": [
        {"line": i["line"], "action": i["action"], "record": i["record"], "hash": i.get("hash")} for i in out]}
    db.execute("INSERT INTO previews(token,payload,created) VALUES(?,?,?)", (token, json.dumps(payload), datetime.now().isoformat()))
    db.commit()
    return {"token": token, "filename": filename, "layout": layout, "sha256": sha, "summary": summary,
            "already_imported": dict(already) if already else None, "rows": [
                {k: v for k, v in i.items() if k != "record"} | {"status": (i["record"] or {}).get("status")} for i in out]}


def commit(db, token: str) -> dict:
    r = db.execute("SELECT payload FROM previews WHERE token=?", (token,)).fetchone()
    if not r:
        raise KeyError("Náhled importu nenalezen nebo už byl uložen.")
    p = json.loads(r["payload"])
    now = datetime.now().isoformat(timespec="seconds")
    cur = db.execute("INSERT INTO imports(filename,sha256,imported_at) VALUES(?,?,?)", (p["filename"], p["sha256"], now))
    batch = cur.lastrowid
    created = updated = unchanged = skipped = 0
    for it in p["items"]:
        rec = it["record"]
        if not rec or it["action"] in ("error", "duplicate"):
            skipped += 1
            continue
        ex = db.execute("SELECT id, content_hash FROM obligations WHERE code=?", (rec["code"],)).fetchone()
        if ex and ex["content_hash"] == it["hash"]:
            unchanged += 1
            continue
        vals = [rec[f] for f in DB_FIELDS]
        if ex:
            sets = ",".join(f"{f}=?" for f in DB_FIELDS)
            db.execute(f"UPDATE obligations SET {sets}, content_hash=?, batch_id=?, updated_at=?, is_demo=? WHERE id=?",
                       vals + [it["hash"], batch, now, 1 if p["filename"].startswith("demo") else 0, ex["id"]])
            updated += 1
        else:
            cols = ",".join(DB_FIELDS)
            db.execute(f"INSERT INTO obligations({cols},content_hash,batch_id,updated_at,is_demo) VALUES({','.join('?' * len(DB_FIELDS))},?,?,?,?)",
                       vals + [it["hash"], batch, now, 1 if p["filename"].startswith("demo") else 0])
            created += 1
    db.execute("UPDATE imports SET created=?,updated=?,unchanged=?,skipped=? WHERE id=?", (created, updated, unchanged, skipped, batch))
    db.execute("DELETE FROM previews WHERE token=?", (token,))
    db.commit()
    return {"batch": batch, "created": created, "updated": updated, "unchanged": unchanged, "skipped": skipped}
