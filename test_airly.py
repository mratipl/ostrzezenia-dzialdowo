"""Testy Airly: budżet zapytań, kadencja, prezentacja. Bez sieci."""
import json, os, pathlib
from kolektor import siec

N = {"zapytania": 0}

def pomiar_dla(pm25, pm10, poziom, opis):
    return {"current": {"values": [{"name": "PM25", "value": pm25},
                                   {"name": "PM10", "value": pm10}],
                        "indexes": [{"name": "AIRLY_CAQI", "value": pm25 * 2,
                                     "level": poziom, "description": opis}]}}

ODPOWIEDZI = {
    "10303": pomiar_dla(41.0, 58.0, "HIGH", "Powietrze jest złej jakości."),
    "10343": pomiar_dla(12.0, 18.0, "LOW", "Powietrze jest dobrej jakości."),
    "10349": pomiar_dla(23.0, 34.0, "MEDIUM", "Powietrze jest średniej jakości."),
}

def fałszywy(url, naglowki=None, proby=None, zapasowy_ua=True):
    N["zapytania"] += 1
    assert naglowki and "apikey" in naglowki, "brak nagłówka apikey"
    assert proby == 1, "Airly musi mieć proby=1 — nieudane żądania wliczają się do limitu"
    assert zapasowy_ua is False, "Airly nie może próbować drugiego User-Agenta"
    for ident, odp in ODPOWIEDZI.items():
        if ident in url:
            return odp
    raise siec.BladPobierania("nieobsłużony adres")

from kolektor.zrodla import airly
airly.pobierz_json = fałszywy

print("== bez klucza: zero zapytań ==")
os.environ.pop("AIRLY_KLUCZ", None)
w = airly.pomiar()
assert not w.status.ok and w.status.uwaga.startswith("nieaktywne")
assert N["zapytania"] == 0
print("   ok —", w.status.uwaga)

print("\n== pomiar z trzech czujników ==")
os.environ["AIRLY_KLUCZ"] = "test"
w = airly.pomiar()
for p in w.pozycje:
    print(f"   [{p.stopien}] {p.tytul}: {p.opis}")
assert w.status.ok and len(w.pozycje) == 3
assert w.pozycje[0].stopien == 2, "najgorszy odczyt musi być pierwszy"
assert N["zapytania"] == 3, f"budżet: oczekiwano 3 zapytań, było {N['zapytania']}"
print("   zapytań:", N["zapytania"], "| uwaga:", w.status.uwaga)

print("\n== budżet dobowy ==")
NA_CYKL, CYKLI = 3, 24
print(f"   {NA_CYKL} zapytania × {CYKLI} cykli = {NA_CYKL*CYKLI} na dobę (limit 100)")
assert NA_CYKL * CYKLI <= 100

print("\n== kadencja: drugi przebieg w tej samej godzinie nie pyta ==")
from kolektor.main import zbierz, WYJSCIE
import kolektor.zrodla.imgw as imgw, kolektor.zrodla.gios as gios
import kolektor.zrodla.open_meteo as om

def pusto(*a, **k):
    raise siec.BladPobierania("wyłączone w teście")
for m in (imgw, gios, om):
    m.pobierz_json = pusto
    if hasattr(m, "pobierz_tekst"):
        m.pobierz_tekst = pusto

WYJSCIE.mkdir(parents=True, exist_ok=True)
przed = N["zapytania"]
zbierz()
po_pierwszym = N["zapytania"]
print(f"   przebieg 1: {po_pierwszym - przed} zapytań do Airly")
zbierz()
print(f"   przebieg 2: {N['zapytania'] - po_pierwszym} zapytań do Airly")
assert N["zapytania"] == po_pierwszym, "kadencja nie zadziałała — limit zostanie wyczerpany"

dane = json.loads((WYJSCIE / "dane.json").read_text(encoding="utf-8"))
airly_stan = [z for z in dane["zrodla"] if z["id"] == "airly"][0]
print("   status:", airly_stan["ok"], "|", airly_stan["uwaga"])
assert airly_stan["ok"] and "pamięci" in airly_stan["uwaga"]
assert len([p for p in dane["stany"] if p["zrodlo"] == "airly"]) == 3, \
    "dane z pamięci muszą zostać przeniesione"

print("\nWszystkie kontrole przeszły.")
