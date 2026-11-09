"""Spouštěč: nainstaluje závislosti, spustí aplikaci a otevře prohlížeč.
Spuštění:  python start.py   (Windows: poklepejte na run.bat, macOS: start.command)"""
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

PORT = 8000
URL = f"http://127.0.0.1:{PORT}"

print("Instaluji závislosti (poprvé to chvíli trvá)…")
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
if r.returncode:
    print("\nINSTALACE SELHALA. Zkontrolujte připojení k internetu a že máte Python 3.10 nebo novější.")
    input("Stiskněte Enter pro zavření…")
    sys.exit(1)


def open_when_ready():
    for _ in range(60):
        try:
            urllib.request.urlopen(URL + "/api/meta", timeout=1)
            webbrowser.open(URL)
            print(f"\nAplikace běží na {URL}  (okno nechte otevřené, zavřením se aplikace ukončí)")
            return
        except Exception:
            time.sleep(0.5)


threading.Thread(target=open_when_ready, daemon=True).start()
try:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT)
except OSError:
    print(f"\nPort {PORT} je obsazený. Zavřete jinou běžící kopii aplikace a zkuste to znovu.")
    input("Stiskněte Enter pro zavření…")
