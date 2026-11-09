# Pokyny pro projekt Mapa předkládání
- Jazyk uživatelského rozhraní a dokumentace: čeština.
- Do repozitáře patří jen kód, dokumentace a **syntetická** data. Nikdy neukládat interní podklady ECRU (xlsx), reálné databáze, tokeny ani `.env`.
- Neověřené pravidlo (`status != potvrzeno`) se nesmí zobrazit jako potvrzená povinnost; kontrolu drží `service.is_confirmed`.
- Logika plánování: `app/engine.py`; kontrola programu a kalendář: `app/service.py`; import: `app/importer.py`.
- Testy: `python3 -m pytest`; před změnou výpočtů spusťte `tests/test_acceptance.py`.
- Změny dělat ve vlastní větvi, rozpracovanou práci ostatních zachovat.
