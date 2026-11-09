"""Vygeneruje data/demo_map.csv, data/import_template.csv a data/demo_meetings.json (SYNTETICKÁ DATA)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.importer import NATIVE_FIELDS  # noqa: E402

D = Path(__file__).resolve().parent.parent / "data"
PR, DR, VH = "představenstvo", "dozorčí rada", "valná hromada"
ACC, GOV, RISK, REM, COMP = "Účetnictví a audit", "Korporátní řízení", "Řízení rizik", "Odměňování", "Compliance"
n = [0]


def row(duty, step, role, subject, organ, act, area, typ, *, cond="", exc="", follow="", dk="none", dates="", months="",
        dtext="", prep=14, gap=0, docs="", agenda="", res="", trig="", kw="", applic="vzdy", ok=True, reason="",
        ref=None, eff="2026-01-01"):
    n[0] += 1
    r = dict.fromkeys(NATIVE_FIELDS, "")
    r.update(kod=f"{duty}-{step}", kod_povinnosti=duty, krok=step, role=role, predmet=subject, organ=organ, ukon=act,
             oblast=area, typ=typ, pouzitelnost=applic, podminky=cond, vyjimky=exc, navaznosti=follow, lhuta_typ=dk,
             lhuta_data=dates, lhuta_mesicu=months, lhuta_text=dtext, priprava_dnu=prep, odstup_dnu=gap, podklady=docs,
             bod_programu=agenda or subject, navrh_usneseni=res, spoustec=trig, klicova_slova=kw)
    if ok:
        r.update(zdroj="DEMO – syntetický podklad (není zdrojem ECRU)", clanek=ref or f"DEMO čl. {n[0]}", verze="demo-1",
                 ucinnost_od=eff, overeno_dne="2026-11-01", stav="potvrzeno")
    else:
        r.update(zdroj="DEMO", clanek=ref or "", verze="", ucinnost_od="", overeno_dne="", stav="K ověření", duvod_k_overeni=reason)
    return r


R = []
# --- Účetní závěrka (periodická, řetězec PŘ -> DR -> VH)
R += [
    row("ZAV", 1, "předloží", "Řádná účetní závěrka", PR, "schválení", ACC, "periodická", dk="after_fy_end", months=3,
        dtext="do 3 měsíců od konce účetního období", prep=21, docs="Účetní závěrka, zpráva auditora", agenda="Účetní závěrka – schválení návrhu pro dozorčí radu a valnou hromadu",
        res="Představenstvo schvaluje řádnou účetní závěrku za uplynulé období a předkládá ji dozorčí radě.", kw="uzaverka financni vykazy"),
    row("ZAV", 2, "přezkoumá", "Řádná účetní závěrka", DR, "projednání", ACC, "periodická", dtext="před valnou hromadou", gap=14,
        prep=7, docs="Účetní závěrka, zpráva auditora", agenda="Účetní závěrka – přezkum dozorčí radou", res="Dozorčí rada přezkoumala účetní závěrku a doporučuje valné hromadě její schválení."),
    row("ZAV", 3, "schválí", "Řádná účetní závěrka", VH, "schválení", ACC, "periodická", dk="fixed", dates="6-30", dtext="30. 6.", gap=14, prep=30,
        docs="Účetní závěrka, zpráva DR, pozvánka", agenda="Schválení řádné účetní závěrky", res="Valná hromada schvaluje řádnou účetní závěrku za uplynulé období."),
]
# --- Určení auditora (periodické) + změna auditora (událost)
R += [
    row("AUD", 1, "navrhne", "Určení auditora", PR, "projednání", ACC, "periodická", prep=14, docs="Nabídky auditorů", agenda="Návrh auditora pro příští období", kw="auditor"),
    row("AUD", 2, "vyjádří se", "Určení auditora", DR, "vyjádření", ACC, "periodická", gap=7, prep=7, agenda="Vyjádření k návrhu auditora"),
    row("AUD", 3, "určí", "Určení auditora", VH, "rozhodnutí", ACC, "periodická", dk="fixed", dates="6-30", dtext="30. 6.", gap=7, prep=30, agenda="Určení auditora",
        res="Valná hromada určuje auditorem pro účetní závěrku společnost [doplnit]."),
    row("AUDZM", 1, "navrhne", "Změna auditora", PR, "projednání", ACC, "událost", trig="auditor_change", prep=14, docs="Návrh nového auditora, důvod změny",
        agenda="Změna auditora – návrh představenstva", kw="zmena auditora novy auditor vymena auditora",
        follow="Po schválení: smlouva s novým auditorem, oznámení regulátorovi (DEMO)"),
    row("AUDZM", 2, "vyjádří se", "Změna auditora", DR, "vyjádření", ACC, "událost", trig="auditor_change", gap=7, prep=7, agenda="Změna auditora – vyjádření dozorčí rady"),
    row("AUDZM", 3, "schválí", "Změna auditora", VH, "schválení", ACC, "událost", trig="auditor_change", gap=7, prep=30, agenda="Změna auditora – schválení",
        res="Valná hromada schvaluje změnu auditora a určuje auditorem [doplnit]."),
]
# --- Odměňování / bonusy
R += [
    row("BONST", 1, "navrhne", "Pohyblivá složka odměny členů představenstva (bonusy)", PR, "projednání", REM, "periodická", trig="remuneration",
        cond="Platí, pokud je členům představenstva vyplácena pohyblivá složka odměny (bonus, tantiéma).", prep=21,
        docs="Návrh výše bonusů, vyhodnocení výkonnosti", agenda="Výše bonusů členů představenstva – návrh", kw="bonus bonusy tantiema premie"),
    row("BONST", 2, "vyjádří se", "Pohyblivá složka odměny členů představenstva (bonusy)", DR, "vyjádření", REM, "periodická", trig="remuneration",
        cond="Platí, pokud je členům představenstva vyplácena pohyblivá složka odměny.", gap=10, prep=7, agenda="Bonusy členů představenstva – vyjádření dozorčí rady"),
    row("BONST", 3, "schválí", "Pohyblivá složka odměny členů představenstva (bonusy)", VH, "rozhodnutí", REM, "periodická", trig="remuneration",
        cond="Platí, pokud je členům představenstva vyplácena pohyblivá složka odměny.", dk="fixed", dates="6-30", dtext="30. 6.", gap=7, prep=30,
        agenda="Rozhodnutí o výši bonusů členů představenstva", res="Valná hromada schvaluje pohyblivou složku odměny členů představenstva ve výši [doplnit]."),
    row("BONZAM", 1, "schválí", "Pohyblivá složka odměny zaměstnanců a významných pracovníků", PR, "schválení", REM, "periodická", trig="remuneration",
        cond="Platí pro pracovníky, jejichž činnost má významný vliv na rizikový profil společnosti.", exc="Neplatí pro ostatní zaměstnance (řeší vedení).",
        dk="fixed", dates="3-31", dtext="31. 3.", applic="podmíněně", prep=14, docs="Zásady odměňování, přehled příjemců", agenda="Pohyblivá složka odměny – významní pracovníci",
        kw="bonus pohyblive slozky odmeny odmenovani"),
    row("BONZAM", 2, "projedná", "Pohyblivá složka odměny zaměstnanců a významných pracovníků", DR, "projednání", REM, "periodická", trig="remuneration",
        cond="Platí pro pracovníky s významným vlivem na rizikový profil.", gap=7, prep=7, applic="podmíněně", agenda="Vyhodnocení systému odměňování"),
    row("ODMCL", 1, "navrhne", "Odměna člena voleného orgánu", PR, "projednání", REM, "událost", trig="remuneration", prep=14, agenda="Odměna člena orgánu – návrh", kw="odmena tantiema"),
    row("ODMCL", 2, "vyjádří se", "Odměna člena voleného orgánu", DR, "vyjádření", REM, "událost", trig="remuneration", gap=7, prep=7, agenda="Odměna člena orgánu – vyjádření DR"),
    row("ODMCL", 3, "schválí", "Odměna člena voleného orgánu", VH, "schválení", REM, "událost", trig="remuneration", gap=7, prep=30, agenda="Schválení odměny člena orgánu"),
    row("SMLF", 1, "navrhne", "Smlouva o výkonu funkce", PR, "projednání", GOV, "událost", trig="office_contract", prep=14, agenda="Smlouva o výkonu funkce – návrh", kw="smlouva o vykonu funkce manazerska smlouva"),
    row("SMLF", 2, "schválí", "Smlouva o výkonu funkce", VH, "schválení", GOV, "událost", trig="office_contract", gap=7, prep=30, agenda="Schválení smlouvy o výkonu funkce včetně změn"),
]
# --- Změna člena orgánu
R += [
    row("CLPR", 1, "navrhne", "Volba / odvolání člena představenstva", PR, "projednání", GOV, "událost", trig="member_change",
        cond="Platí při změně člena představenstva.", prep=14, agenda="Změna člena představenstva – návrh", kw="clen predstavenstva zmena clena volba odvolani"),
    row("CLPR", 2, "volí", "Volba / odvolání člena představenstva", VH, "rozhodnutí", GOV, "událost", trig="member_change",
        cond="Platí při změně člena představenstva.", gap=7, prep=30, agenda="Volba / odvolání člena představenstva"),
    row("CLDR", 1, "navrhne", "Volba / odvolání člena dozorčí rady", DR, "projednání", GOV, "událost", trig="member_change",
        cond="Platí při změně člena dozorčí rady.", prep=14, agenda="Změna člena dozorčí rady – návrh"),
    row("CLDR", 2, "volí", "Volba / odvolání člena dozorčí rady", VH, "rozhodnutí", GOV, "událost", trig="member_change",
        cond="Platí při změně člena dozorčí rady.", gap=7, prep=30, agenda="Volba / odvolání člena dozorčí rady"),
]
# --- Významná smlouva, majetek, outsourcing, předpisy, střet zájmů
R += [
    row("VYZN", 1, "navrhne", "Významná smlouva nebo majetková transakce", PR, "projednání", GOV, "událost", trig="major_transaction",
        cond="Hodnota nad demonstračním limitem 2 000 000 Kč nebo mimo běžný obchodní styk.", prep=10, docs="Návrh smlouvy, ocenění", agenda="Významná smlouva / majetková transakce – návrh",
        kw="majetkova transakce koupe prodej zcizeni nabyti vyznamna smlouva"),
    row("VYZN", 2, "schválí", "Významná smlouva nebo majetková transakce", DR, "schválení", GOV, "událost", trig="major_transaction",
        cond="Hodnota nad demonstračním limitem 2 000 000 Kč nebo mimo běžný obchodní styk.", gap=5, prep=7, agenda="Schválení významné smlouvy / majetkové transakce",
        res="Dozorčí rada schvaluje uzavření smlouvy [doplnit] v hodnotě [doplnit]."),
    row("OUTS", 1, "schválí", "Zavedení nebo změna outsourcingu", PR, "schválení", RISK, "událost", trig="outsourcing", prep=14, docs="Posouzení rizik outsourcingu, návrh smlouvy",
        agenda="Outsourcing – schválení", kw="outsourcing externalizace delegovani"),
    row("OUTS", 2, "vezme na vědomí", "Zavedení nebo změna outsourcingu", DR, "vzetí na vědomí", RISK, "událost", trig="outsourcing", gap=0, prep=7, agenda="Outsourcing – informace pro dozorčí radu"),
    row("OUTSR", 1, "schválí", "Roční zpráva o kontrole outsourcovaných činností", PR, "schválení", RISK, "periodická", dk="fixed", dates="4-30", dtext="30. 4.", prep=14, agenda="Zpráva o kontrole outsourcingu"),
    row("VNIT", 1, "schválí", "Změna vnitřního předpisu", PR, "schválení", COMP, "událost", trig="internal_regulation", prep=10, docs="Návrh změny, srovnávací tabulka",
        agenda="Změna vnitřního předpisu – schválení", kw="vnitrni predpis smernice politika"),
    row("VNIT", 2, "vezme na vědomí", "Změna vnitřního předpisu", DR, "vzetí na vědomí", COMP, "událost", trig="internal_regulation", gap=0, prep=7, agenda="Změna vnitřního předpisu – informace DR"),
    row("STRET", 1, "posoudí", "Střet zájmů", PR, "rozhodnutí", COMP, "událost", trig="conflict_of_interest", prep=3, docs="Popis střetu zájmů, navržená opatření",
        agenda="Střet zájmů – posouzení a opatření", kw="stret zajmu konflikt zajmu"),
    row("STRET", 2, "vezme na vědomí", "Střet zájmů", DR, "vzetí na vědomí", COMP, "událost", trig="conflict_of_interest", gap=0, prep=7, agenda="Střet zájmů – informace DR"),
]
# --- Další periodické povinnosti
R += [
    row("AML", 1, "schválí", "Roční hodnotící zpráva AML", PR, "schválení", COMP, "periodická", dk="fixed", dates="4-30", dtext="do konce 4. měsíce", prep=14, agenda="AML – roční hodnotící zpráva"),
    row("ZDR", 1, "vytvoří", "Zpráva o činnosti dozorčí rady", DR, "projednání", GOV, "periodická", dk="fixed", dates="6-30", dtext="30. 6.", prep=14, agenda="Zpráva o činnosti dozorčí rady"),
    row("ZDR", 2, "vezme na vědomí", "Zpráva o činnosti dozorčí rady", VH, "vzetí na vědomí", GOV, "periodická", dk="fixed", dates="6-30", dtext="30. 6.", gap=7, prep=30, agenda="Zpráva dozorčí rady – vzetí na vědomí"),
    row("KVART", 1, "projedná", "Čtvrtletní zpráva o aktivech a zisku", PR, "projednání", ACC, "periodická", dk="fixed", dates="1-31;4-30;7-31;10-31", dtext="31. 1., 30. 4., 31. 7., 31. 10.", prep=7, agenda="Čtvrtletní zpráva"),
    row("RIZ", 1, "schválí", "Souhrnná zpráva o řízení rizik", PR, "schválení", RISK, "periodická", dk="fixed", dates="3-31", dtext="do konce prvního kvartálu", prep=14, agenda="Souhrnná zpráva o řízení rizik"),
    row("COMPL", 1, "projedná", "Plán kontrolní činnosti compliance", PR, "projednání", COMP, "periodická", dk="fixed", dates="1-31", dtext="31. 1.", prep=10, agenda="Plán kontrolní činnosti compliance"),
    row("COMPL", 2, "vezme na vědomí", "Plán kontrolní činnosti compliance", DR, "vzetí na vědomí", COMP, "periodická", dk="fixed", dates="1-31", dtext="31. 1.", gap=0, prep=7, agenda="Plán kontrolní činnosti compliance – informace DR"),
    row("PLMOC", 1, "projedná", "Přehled plných mocí", PR, "projednání", GOV, "periodická", dk="fixed", dates="3-31", dtext="31. 3.", prep=7, agenda="Přehled plných mocí"),
    row("SVHR", 1, "rozhodne", "Svolání řádné valné hromady", PR, "rozhodnutí", GOV, "periodická", dk="fixed", dates="5-15", dtext="pozvánka alespoň 30 dnů před valnou hromadou (do 30. 6.)", prep=14,
        agenda="Svolání řádné valné hromady", docs="Pozvánka, návrhy usnesení"),
    row("SZAS", 1, "svolá", "Zasedání dozorčí rady – nejméně 2× ročně", DR, "konání", GOV, "periodická", dtext="nejméně 1× za 6 měsíců", agenda="Plán zasedání dozorčí rady"),
]
# --- K ověření
R += [
    row("PROP", 1, "vyhotoví", "Zpráva o vztazích mezi propojenými osobami", PR, "konání", GOV, "periodická", dtext="lhůta nezjištěna", ok=False,
        reason="Lhůta v podkladu chybí; zdroj nebyl ověřen proti znění předpisu.", agenda="Zpráva o vztazích mezi propojenými osobami"),
    row("OBS", 1, "obsadí", "Obsazení uvolněného místa člena orgánu", VH, "rozhodnutí", GOV, "událost", trig="member_change", ok=False,
        reason="Rozporný podklad: lhůta 2 měsíce ve stanovách vs. jiná lhůta v druhém zdroji.", ref="DEMO čl. ?", agenda="Obsazení uvolněného místa", prep=30),
    row("VYSL", 1, "vyhodnotí", "Vyhodnocení systému odměňování", DR, "vyhodnocení", REM, "periodická", trig="remuneration", ok=False,
        reason="Není určen zdroj ani lhůta.", agenda="Vyhodnocení systému odměňování", kw="odmenovani bonus"),
    row("NOVA", 1, "schválí", "Nová povinnost účinná od 1. 1. 2027", PR, "schválení", COMP, "periodická", dk="fixed", dates="3-31", dtext="31. 3.", eff="2027-01-01",
        agenda="Nová povinnost (zatím neúčinná)", ref="DEMO čl. 99"),
]


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=NATIVE_FIELDS, delimiter=";")
        w.writeheader()
        w.writerows(rows)


write(D / "demo_map.csv", R)
tmpl = [dict.fromkeys(NATIVE_FIELDS, "")]
tmpl[0].update(kod="PRIKLAD-1", kod_povinnosti="PRIKLAD", krok=1, role="schválí", predmet="Příklad povinnosti", organ="představenstvo",
               ukon="schválení", oblast="Korporátní řízení", typ="periodická", pouzitelnost="vzdy", lhuta_typ="fixed", lhuta_data="6-30",
               lhuta_text="30. 6.", priprava_dnu=14, odstup_dnu=0, bod_programu="Příklad bodu programu", spoustec="", zdroj="Název předpisu",
               clanek="čl. X bod Y", verze="1.0", ucinnost_od="2026-01-01", overeno_dne="2026-11-01", stav="potvrzeno")
write(D / "import_template.csv", tmpl)

M = []
for o, ds in {
    "predstavenstvo": ["2026-11-24", "2026-12-15", "2027-01-19", "2027-02-16", "2027-03-16", "2027-04-20", "2027-05-18", "2027-06-08", "2027-09-14"],
    "dozorci_rada": ["2026-12-10", "2027-03-04", "2027-05-27", "2027-09-23"],
    "valna_hromada": ["2027-06-24"],
}.items():
    M += [{"organ": o, "date": d, "note": "DEMO"} for d in ds]
(D / "demo_meetings.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(R), "demo rows")
