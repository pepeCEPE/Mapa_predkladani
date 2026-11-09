# Mapa předkládání (ECRU) – první funkční verze

Aplikace odpovídá na otázku: **co musí který orgán projednat nebo schválit, do kdy a v jakém pořadí.**

> **Data v repozitáři jsou syntetická (DEMO).** Schválená mapa ECRU zde není. Interní podklady, databáze s reálnými daty a přístupové údaje se do repozitáře neukládají (viz `.gitignore`).

## Umístění a práce s repozitářem
- GitHub: https://github.com/pepeCEPE/Mapa_predkladani (soukromý). Vývojová větev: `claude/mapa-predkladani-v1`; do `main` jen přes pull request.
- Google Disk (účet projektu): Můj disk → „Mapa schvalování“ – archiv zdrojových kódů a tento README. Zdrojem pravdy pro kód je GitHub, na Disk se kód neukládá průběžně.
- Do GitHubu patří jen kód, dokumentace a syntetická data. Interní podklady ECRU (xlsx), databáze (`data/*.db`) a přístupové údaje se neukládají – hlídá to `.gitignore`.
- Schválenou mapu ECRU naimportujte lokálně přes záložku Import; zůstane jen v lokální databázi.

## Spuštění
```bash
./run.sh            # nainstaluje závislosti a spustí http://127.0.0.1:8000
python3 -m pytest   # testy
```
Při prvním startu se vytvoří `data/app.db` a načtou se demo data (`data/demo_map.csv`, `data/demo_meetings.json`). Znovu: `python3 -m app.seed --reset`.

## Funkce
- **Přehled** – vyhledávání (bez diakritiky, synonyma: „bonus“ → pohyblivá složka odměny), příští zasedání s počtem povinných bodů, povinnosti na 90 dní, tlačítko „Prověřit program zasedání“.
- **Katalog** – filtry orgán / úkon / oblast / typ / stav, stránkování (testováno na 440 záznamech).
- **Kontrola programu** – „Musí být zařazeno“, „Prověřte, zda se vás týká“, „Mohlo by být vhodné zařadit“; situační checklist Ano/Ne/Nevím; uložení a kopírování programu; stav „není zařazeno“ se odvozuje z uloženého programu (jinak „neznámý“).
- **Kalendář** – roční přehled lhůt a zasedání, doporučení posledního bezpečného zasedání, konflikt / neúplný kalendář, přepočet při změně termínů.
- **Import** – XLSX/CSV, náhled, chyby po řádcích, duplicity a rozpory, idempotentní uložení. Rozpoznává šablonu (`data/import_template.csv`) i sloupce dřívější „Mapy předkládání“ (ty se vždy označí K ověření).

## Pravidla výpočtu
- Pravidlo je **potvrzené** jen s vyplněným zdrojem, článkem, verzí, účinností a datem ověření (a účinností ≤ datu výpočtu). Jinak je **K ověření** s důvodem a nikdy se nezobrazí jako potvrzená povinnost ani mezi „Musí být zařazeno“.
- Krok = řádek; více kroků jedné povinnosti sdílí `kod_povinnosti`, pořadí určuje `krok`. `odstup_dnu` = minimální odstup od zasedání předchozího kroku, `priprava_dnu` = předstih na podklady.
- Doporučení = **poslední zasedání**, na kterém se celý řetězec (včetně předchozích a navazujících kroků jiných orgánů) ještě stihne. Termín přípravy = zasedání − `priprava_dnu`.
- Účetní období končí 31. 12. (nastavitelné `PUT /api/settings`).

## Režim bez termínů zasedání
Pokud v kalendáři nejsou zadána žádná zasedání, aplikace nedoporučuje zasedání, nehlásí neúplný kalendář u každé povinnosti a počítá jen s lhůtami. Kontrola programu pak řadí povinnosti podle lhůty v pokrývaném období (výchozí: 90 dní od zasedání). Po zadání zasedání se doporučení dopočtou.

## Co zatím není
Evidence skutečného plnění povinností, e-mailové připomínky (zatím jen v aplikaci), uživatelé a práva, schválená mapa ECRU (nutno naimportovat).
