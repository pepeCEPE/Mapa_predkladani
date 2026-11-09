"""Ověření podle zadání – na syntetických datech."""
from conftest import OK, import_bytes, make_csv


def test_bonus_najde_pravidlo_poradi_a_zdroj(client):
    r = client.get("/api/search", params={"q": "bonus"}).json()
    assert r["count"] >= 1
    subjects = [x["subject"] for x in r["results"]]
    assert any("Pohyblivá složka odměny členů představenstva" in s for s in subjects)
    rule = next(x for x in r["results"] if x["duty_code"] == "BONST")
    assert [s["organ"] for s in rule["steps"]] == ["predstavenstvo", "dozorci_rada", "valna_hromada"]
    assert [s["step_no"] for s in rule["steps"]] == [1, 2, 3]
    assert rule["steps"][-1]["source_ref"].startswith("DEMO")
    assert rule["conditions"]
    # více pravidel -> každé s podmínkou
    assert {x["duty_code"] for x in r["results"]} >= {"BONST", "BONZAM"}
    assert all(x["conditions"] for x in r["results"] if x["duty_code"] in ("BONST", "BONZAM"))


def test_hledani_bez_diakritiky_a_synonyma(client):
    a = {x["duty_code"] for x in client.get("/api/search", params={"q": "pohyblivá složka odměny"}).json()["results"]}
    b = {x["duty_code"] for x in client.get("/api/search", params={"q": "pohyblive slozky odmeny"}).json()["results"]}
    assert a == b and "BONST" in a
    assert "AUDZM" in {x["duty_code"] for x in client.get("/api/search", params={"q": "vymena auditora"}).json()["results"]}
    assert "VYZN" in {x["duty_code"] for x in client.get("/api/search", params={"q": "prodej majetku"}).json()["results"]}


def test_zmena_auditora_ano_nevim_ne(client):
    base = {"organ": "predstavenstvo", "date": "2027-03-16", "today": "2026-11-09"}
    titles = lambda r, c: [i["title"] for i in r[c]]
    ano = client.post("/api/program/check", json=base | {"answers": {"auditor_change": "ano"}}).json()
    assert "Změna auditora – návrh představenstva" in titles(ano, "must")
    nevim = client.post("/api/program/check", json=base | {"answers": {"auditor_change": "nevim"}}).json()
    assert "Změna auditora – návrh představenstva" in titles(nevim, "check")
    assert "Změna auditora – návrh představenstva" not in titles(nevim, "must")
    ne = client.post("/api/program/check", json=base | {"answers": {"auditor_change": "ne"}}).json()
    for c in ("must", "check", "suggest"):
        assert "Změna auditora – návrh představenstva" not in titles(ne, c)
    # jiný orgán dostane navazující kroky
    assert any(f["duty_code"] == "AUDZM" for f in ano["follow_ups"])


SCEN = [
    dict(OK, kod="T-1", kod_povinnosti="T", krok=1, role="schválí", predmet="Test lhůty", organ="valná hromada", ukon="schválení",
         typ="periodická", lhuta_typ="fixed", lhuta_data="6-30", priprava_dnu=30, bod_programu="Test lhůty"),
    dict(OK, kod="T-2", kod_povinnosti="T", krok=2, role="podá návrh", predmet="Test lhůty", organ="představenstvo", ukon="konání",
         typ="periodická", lhuta_typ="fixed", lhuta_data="6-30", odstup_dnu=10, bod_programu="Test lhůty – navazující krok"),
]


def _setup(client, pr_dates, today_meetings=("2027-04-10", "2027-06-20")):
    import_bytes(client, "scen.csv", make_csv(SCEN))
    for m in client.get("/api/meetings").json():
        client.delete(f"/api/meetings/{m['id']}")
    for d in today_meetings:
        assert client.post("/api/meetings", json={"organ": "valna_hromada", "date": d}).status_code == 200
    for d in pr_dates:
        assert client.post("/api/meetings", json={"organ": "predstavenstvo", "date": d}).status_code == 200


def _rec(client, today):
    return client.post("/api/recommend", json={"duty_code": "T", "today": today}).json()


def test_lhuta_30_6_doporuci_cerven_kdyz_je_cas(client):
    _setup(client, ["2027-04-20", "2027-06-30"])
    p = _rec(client, "2027-02-01")
    assert p["status"] == "ok"
    assert p["steps"][0]["date"] == "2027-06-20"
    assert p["steps"][0]["previous_date"] == "2027-04-10"       # upozornění na předchozí vhodné zasedání
    assert p["steps"][0]["prep_date"] == "2027-05-21"
    assert p["steps"][1]["date"] == "2027-06-30"


def test_lhuta_30_6_doporuci_duben_kdyz_cerven_nestaci(client):
    _setup(client, ["2027-04-20", "2027-06-25"])               # po 20. 6. chybí navazující zasedání PŘ s odstupem
    p = _rec(client, "2027-02-01")
    assert p["status"] == "ok"
    assert p["steps"][0]["date"] == "2027-04-10"
    assert p["steps"][1]["date"] >= "2027-04-20"          # navazující krok PŘ po VH, nejpozději do lhůty


def test_lhuta_30_6_konflikt_kdyz_nevyhovuje_ani_duben(client):
    _setup(client, ["2027-04-20", "2027-06-25"])
    p = _rec(client, "2027-03-20")                             # na podklady pro 10. 4. už není 30 dní
    assert p["status"] == "conflict"
    assert p["best"] is None and p["reasons"]


def test_neuplny_kalendar_se_ohlasi(client):
    _setup(client, ["2027-04-20"], today_meetings=())
    p = _rec(client, "2027-02-01")
    assert p["status"] == "incomplete"
    assert "Kalendář není úplný" in p["reasons"][0]


def test_zmena_terminu_prepocita_doporuceni(client):
    _setup(client, ["2027-04-20", "2027-06-30"])
    assert _rec(client, "2027-02-01")["steps"][0]["date"] == "2027-06-20"
    pm = next(m for m in client.get("/api/meetings").json() if m["date"] == "2027-06-30")
    r = client.delete(f"/api/meetings/{pm['id']}", params={"today": "2027-02-01"}).json()
    assert any(c["duty_code"] == "T" for c in r["changed"])
    assert _rec(client, "2027-02-01")["steps"][0]["date"] == "2027-04-10"


def test_opakovany_import_nezdvoji_zaznamy(client):
    from pathlib import Path
    data = (Path(__file__).resolve().parent.parent / "data" / "demo_map.csv").read_bytes()
    n0 = client.get("/api/obligations", params={"limit": 500}).json()["total"]
    pv = client.post("/api/import/preview", files={"file": ("demo_map.csv", data)}).json()
    assert pv["summary"]["new"] == 0 and pv["summary"]["unchanged"] == n0
    c = client.post("/api/import/commit", json={"token": pv["token"]}).json()
    assert c["created"] == 0 and c["updated"] == 0
    assert client.get("/api/obligations", params={"limit": 500}).json()["total"] == n0
    # změna jednoho řádku = update, ne duplicita
    changed = data.decode("utf-8-sig").replace("Plán kontrolní činnosti compliance;", "Plan kontrolni cinnosti compliance;", 1).encode("utf-8-sig")
    _, c2 = import_bytes(client, "demo_map.csv", changed)
    assert c2["created"] == 0 and c2["updated"] == 1
    assert client.get("/api/obligations", params={"limit": 500}).json()["total"] == n0


def test_neoverene_pravidlo_neni_potvrzena_povinnost(client):
    conf = client.get("/api/obligations", params={"status": "potvrzeno", "limit": 500}).json()["items"]
    codes = {o["duty_code"] for o in conf}
    assert not codes & {"PROP", "OBS", "VYSL"}
    assert all(o["confirmed"] for o in conf)
    # neúčinné pravidlo (účinnost od 1. 1. 2027) není dnes potvrzené, ale po účinnosti ano
    assert "NOVA" not in codes
    # v kontrole programu nikdy mezi "Musí být zařazeno"
    r = client.post("/api/program/check", json={"organ": "valna_hromada", "date": "2027-06-24", "today": "2026-11-09",
                                                  "answers": {"member_change": "ano"}}).json()
    assert all(i["confirmed"] for i in r["must"])
    assert any(i["duty_code"] == "OBS" for i in r["check"])
    obs = next(i for i in r["check"] if i["duty_code"] == "OBS")
    assert obs["unconfirmed_reason"]
    # vyhledávání je označí
    s = client.get("/api/search", params={"q": "propojenými osobami"}).json()["results"][0]
    assert s["confirmed"] is False


def test_program_bez_duplicit_a_stav_zarazeno(client):
    body = {"organ": "predstavenstvo", "date": "2027-03-16", "today": "2026-11-09", "answers": {"auditor_change": "ano"}}
    r = client.post("/api/program/check", json=body).json()
    assert all(i["in_program"] == "neznámý" for i in r["must"])      # program není uložen
    items = [{"obligation_id": i["obligation_id"], "title": i["title"], "act_type": i["act_type"]} for i in r["must"]]
    items += items[:1] + [{"obligation_id": None, "title": items[0]["title"].upper()}]   # duplicity
    s = client.post("/api/programs", json={"organ": "predstavenstvo", "date": "2027-03-16", "items": items}).json()
    assert s["count"] == len(r["must"])
    assert s["text"].count(r["must"][0]["title"]) == 1
    r2 = client.post("/api/program/check", json=body).json()
    assert all(i["in_program"] == "ano" for i in r2["must"])
    # uložený program, ale bod v něm není
    client.post("/api/programs", json={"organ": "predstavenstvo", "date": "2027-03-16", "items": items[:1]})
    r3 = client.post("/api/program/check", json=body).json()
    assert any(i["in_program"] == "ne" for i in r3["must"])


def test_import_nahled_chyby_po_radcich(client):
    rows = [dict(OK, kod="E-1", predmet="", organ="valná hromada", ukon="schválení", typ="periodická"),
            dict(OK, kod="E-2", predmet="Špatný orgán", organ="ředitel", ukon="schválení", typ="periodická"),
            dict(OK, kod="E-3", predmet="Dobrý", organ="dozorčí rada", ukon="projednání", typ="událost"),
            dict(OK, kod="E-3", predmet="Dobrý", organ="dozorčí rada", ukon="projednání", typ="událost"),
            dict(OK, kod="E-4", predmet="Bez podkladu", organ="dozorčí rada", ukon="projednání", typ="událost", clanek="", verze="")]
    pv = client.post("/api/import/preview", files={"file": ("x.csv", make_csv(rows))}).json()
    by = {r["code"]: r for r in pv["rows"]}
    assert by["E-1"]["action"] == "error" and by["E-2"]["action"] == "error"
    assert any("Neznámý orgán" in e for e in by["E-2"]["errors"])
    assert pv["summary"]["duplicate"] == 1
    assert by["E-4"]["status"] == "k_overeni"
    c = client.post("/api/import/commit", json={"token": pv["token"]}).json()
    assert c["created"] == 2 and c["skipped"] == 3
    assert client.post("/api/import/commit", json={"token": pv["token"]}).status_code == 404


def test_import_xlsx_ve_formatu_mapy_je_vse_k_overeni(client, tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mapa předkládání"])
    ws.append(["Číslo povinnosti", "Souvisí s číslem povinnosti", "Označení", "Druh", "Způsob vyřízení", "Výskyt", "Lhůta", "Orgán", "Obsah povinnosti",
               "Bližší určení obsahu", "Odpovědný subjekt", "Schvalovatel 1", "Schvalovatel 2", "Zdroje povinnosti", "Proces", "Reporting ČNB", "Reporting JTFG"])
    ws.append([901, None, "Demo zpráva", "Periodická zpráva", "schválení", "1 x ročně", "30. 6.", "valná hromada", "x", "y", "", "", "", "čl. 1 stanov", "p", "", ""])
    ws.append([902, None, "Demo bez zdroje", "Periodická zpráva", "projednání", "1 x ročně", "do 3 měsíců od skončení účetního období", "představenstvo", "x", "y", "", "", "", "[nečitelné]", "p", "", ""])
    ws.append([903, None, "Demo bez zdroje", "Periodická zpráva", "projednání", "1 x ročně", "31. 3.", "představenstvo", "x", "y", "", "", "", "", "p", "", ""])
    p = tmp_path / "mapa.xlsx"
    wb.save(p)
    pv, c = import_bytes(client, "mapa.xlsx", p.read_bytes())
    assert pv["layout"] == "ecru" and c["created"] == 3
    assert pv["summary"]["k_overeni"] == 3                      # chybí verze/účinnost/ověření
    rows = [o for o in client.get("/api/obligations", params={"limit": 500}).json()["items"] if o["code"].startswith("MAPA-")]
    assert {o["code"] for o in rows} == {"MAPA-901", "MAPA-902", "MAPA-903"} and not any(o["confirmed"] for o in rows)
    after = next(o for o in rows if o["code"] == "MAPA-902")
    assert after["deadline_kind"] == "after_fy_end" and after["deadline_months"] == 3
    # stejné předměty s jiným zdrojem/lhůtou = možný rozpor
    assert any("rozpor" in w for r in pv["rows"] for w in r["warnings"])


def test_katalog_stovky_zaznamu_a_filtry(client, tmp_path):
    import subprocess
    import sys
    out = tmp_path / "large.csv"
    subprocess.run([sys.executable, "scripts/gen_large_demo.py", "400", str(out)], check=True, cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    pv, c = import_bytes(client, "large.csv", out.read_bytes())
    assert c["created"] == 400
    r = client.get("/api/obligations", params={"limit": 50}).json()
    assert r["total"] >= 440 and len(r["items"]) == 50
    f = client.get("/api/obligations", params={"organ": "dozorci_rada", "kind": "periodic", "limit": 500}).json()
    assert f["total"] > 0 and all(i["organ"] == "dozorci_rada" and i["kind"] == "periodic" for i in f["items"])
    ok = client.get("/api/obligations", params={"status": "k_overeni", "limit": 500}).json()
    assert all(not i["confirmed"] for i in ok["items"])


def test_dashboard_a_kalendar(client):
    d = client.get("/api/dashboard", params={"today": "2026-11-09"}).json()
    assert {m["organ"] for m in d["next_meetings"]} == {"predstavenstvo", "dozorci_rada", "valna_hromada"}
    pr = next(m for m in d["next_meetings"] if m["organ"] == "predstavenstvo")
    assert pr["date"] == "2026-11-24" and isinstance(pr["must"], int)
    d2 = client.get("/api/dashboard", params={"today": "2027-02-01"}).json()
    assert d2["upcoming"] and all(i["confirmed"] for i in d2["upcoming"])
    assert all(not i["confirmed"] for i in d2["upcoming_unverified"])
    cal = client.get("/api/calendar", params={"year": 2027, "today": "2026-11-09"}).json()
    assert cal["items"] and cal["meetings"]
    zav = [i for i in cal["items"] if i["duty_code"] == "ZAV" and i["organ"] == "valna_hromada"][0]
    assert zav["deadline"] == "2027-06-30" and zav["recommended"] == "2027-06-24" and zav["prep_date"] < zav["recommended"]
    cal2 = client.get("/api/calendar", params={"year": 2030, "today": "2026-11-09"}).json()
    assert set(cal2["incomplete"]) == {"predstavenstvo", "dozorci_rada", "valna_hromada"}
