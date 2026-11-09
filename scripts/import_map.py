"""Import schválené mapy do lokální databáze (bez demo dat).

python3 scripts/import_map.py mapa.xlsx --zdroj "Stanovy ECRU" --verze "NZ 1021/2026" --ucinnost 2026-10-01 --overeno 2026-11-09 [--reset]
Databáze (data/app.db) je lokální a není v gitu.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import importer  # noqa: E402
from app.db import connect  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--zdroj", default="")
ap.add_argument("--verze", required=True)
ap.add_argument("--ucinnost", required=True)
ap.add_argument("--overeno", required=True)
ap.add_argument("--reset", action="store_true", help="nejdřív smazat pravidla, zasedání a programy (včetně demo dat)")
a = ap.parse_args()
db = connect()
if a.reset:
    for t in ("obligations", "meetings", "programs", "imports", "previews"):
        db.execute(f"DELETE FROM {t}")
    db.commit()
data = Path(a.file).read_bytes()
pv = importer.build_preview(db, Path(a.file).name, data, date.today(),
                            {"zdroj": a.zdroj, "verze": a.verze, "ucinnost_od": a.ucinnost, "overeno_dne": a.overeno})
print("náhled:", pv["summary"])
print("uloženo:", importer.commit(db, pv["token"]))
