"""Test górnej granicy przenoszenia danych z niedziałającego źródła.

Jako źródło przykładowe używamy PSE, nie GIOŚ — GIOŚ jest wyłączony
(najbliższe stacje to Ciechanów i Ostróda, za daleko dla powiatu).
"""
import json
from datetime import timedelta
from kolektor import siec
from kolektor.model import teraz
import kolektor.main as M

# wszystkie źródła padają — liczy się tylko to, co przenosimy z pamięci
def pusto(*a, **k):
    raise siec.BladPobierania("wyłączone w teście")
for modul in ("imgw", "gios", "open_meteo", "gddkia", "airly", "rcb",
              "lasy", "pse", "gminy"):
    m = __import__(f"kolektor.zrodla.{modul}", fromlist=["x"])
    for nazwa in ("pobierz_json", "pobierz_tekst"):
        if hasattr(m, nazwa):
            setattr(m, nazwa, pusto)
import kolektor.zrodla.html_pomoc as H
H.pobierz_tekst = pusto

def przygotuj_pamiec(minut_temu: int):
    """Zapisuje dane.json z odczytem GIOŚ sprzed podanej liczby minut."""
    M.WYJSCIE.mkdir(parents=True, exist_ok=True)
    znacznik = (teraz() - timedelta(minutes=minut_temu)).isoformat(timespec="seconds")
    (M.WYJSCIE / "dane.json").write_text(json.dumps({
        "zrodla": [{"id": "pse", "nazwa": "PSE – bilans mocy",
                    "ok": True, "pobrano": znacznik}],
        "zdarzenia": [],
        "stany": [{"zrodlo": "pse", "charakter": "stan", "typ": "System elektroenergetyczny",
                   "tytul": "Dane operacyjne PSE dostępne", "opis": "",
                   "stopien": 0, "obowiazuje_od": None, "obowiazuje_do": None}],
    }, ensure_ascii=False), encoding="utf-8")

def ile_kafelek() -> int:
    dane = json.loads((M.WYJSCIE / "dane.json").read_text(encoding="utf-8"))
    return len([p for p in dane["stany"] if p["zrodlo"] == "pse"])

from kolektor.konfiguracja import MAKS_WIEK_PRZENOSZENIA_MIN as GRANICA
print(f"granica przenoszenia: {GRANICA} min\n")

print("== dane sprzed 2 godz. — jeszcze pokazywane ==")
przygotuj_pamiec(120)
M.zbierz()
n = ile_kafelek()
print(f"   kafelek PSE: {n}")
assert n == 1, "świeża awaria musi zachować ostatni znany odczyt"

print("\n== dane sprzed 20 godz. — usunięte z tablicy ==")
przygotuj_pamiec(1200)
M.zbierz()
n = ile_kafelek()
print(f"   kafelek PSE: {n}")
assert n == 0, "odczyt sprzed prawie doby nie może wisieć na tablicy"

dane = json.loads((M.WYJSCIE / "dane.json").read_text(encoding="utf-8"))
zrodlo = [z for z in dane["zrodla"] if z["id"] == "pse"][0]
print("   status źródła:", "niedostępne" if not zrodlo["ok"] else "aktualne")
assert not zrodlo["ok"], "źródło musi zostać oznaczone jako niedostępne"
print("   nagłówek:", dane["naglowek"])

print("\nKontrole przenoszenia przeszły.")
