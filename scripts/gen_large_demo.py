"""Vygeneruje syntetický CSV s N záznamy (test škálování katalogu). Použití: python scripts/gen_large_demo.py 300 out.csv"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.importer import NATIVE_FIELDS  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
out = sys.argv[2] if len(sys.argv) > 2 else "large_demo.csv"
random.seed(7)
organs = ["představenstvo", "dozorčí rada", "valná hromada"]
acts = ["schválení", "projednání", "rozhodnutí", "vyhodnocení", "vzetí na vědomí"]
areas = ["Účetnictví a audit", "Korporátní řízení", "Řízení rizik", "Odměňování", "Compliance", "IT a odolnost"]
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=NATIVE_FIELDS, delimiter=";")
    w.writeheader()
    for i in range(1, n + 1):
        r = dict.fromkeys(NATIVE_FIELDS, "")
        periodic = random.random() < 0.5
        r.update(kod=f"SYN-{i:04d}", kod_povinnosti=f"SYN-{i:04d}", krok=1, predmet=f"Syntetická povinnost č. {i}",
                 organ=random.choice(organs), ukon=random.choice(acts), oblast=random.choice(areas),
                 typ="periodická" if periodic else "událost", lhuta_typ="fixed" if periodic else "none",
                 lhuta_data=f"{random.randint(1, 12)}-{random.randint(1, 28)}" if periodic else "",
                 priprava_dnu=14, odstup_dnu=0, bod_programu=f"Bod programu {i}", zdroj="SYNTETICKÝ", clanek=f"čl. {i}",
                 verze="syn-1", ucinnost_od="2026-01-01", overeno_dne="2026-11-01", stav="potvrzeno" if i % 7 else "K ověření",
                 duvod_k_overeni="" if i % 7 else "Syntetický důvod")
        w.writerow(r)
print(out, n)
