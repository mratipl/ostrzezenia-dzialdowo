"""Testy Airly: budżet zapytań, kadencja, prezentacja. Bez sieci."""
import json, os, pathlib
from kolektor import siec

N = {"zapytania": 0}

from datetime import timedelta
from kolektor.model import teraz as _teraz

def pomiar_dla(pm25, pm10, poziom, opis, godzin_temu=0):
    znacznik = (_teraz() - timedelta(hours=godzin_temu)).isoformat()
    return {"current": {"fromDateTime": znacznik, "tillDateTime": znacznik,
                        "values": [{"name": "PM25", "value": pm25},
                                   {"name": "PM10", "value": pm10}],
                        "indexes": [{"name": "AIRLY_CAQI", "value": pm25 * 2,
                                     "level": poziom, "description": opis}]}}

ODPOWIEDZI = {
    "10298": pomiar_dla(41.0, 58.0, "HIGH", "Powietrze jest złej jakości."),
    "10286": pomiar_dla(12.0, 18.0, "LOW", "Powietrze jest dobrej jakości."),
    "10291": pomiar_dla(19.0, 27.0, "MEDIUM", "Powietrze jest średniej jakości."),
    "10288": pomiar_dla(11.0, 16.0, "LOW", "Powietrze jest dobrej jakości."),
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

print("\n== pomiar ze wszystkich czujników ==")
os.environ["AIRLY_KLUCZ"] = "test"
w = airly.pomiar()
for p in w.pozycje:
    print(f"   [{p.stopien}] {p.tytul}: {p.opis}")
assert w.status.ok and len(w.pozycje) == 5
assert w.pozycje[0].stopien == 2, "najgorszy odczyt musi być pierwszy"
assert N["zapytania"] == 5, f"budżet: oczekiwano 5 zapytań, było {N['zapytania']}"
print("   zapytań:", N["zapytania"], "| uwaga:", w.status.uwaga)

print("\n== martwy czujnik nie może udawać stanu bieżącego ==")
MARTWY = dict(ODPOWIEDZI)
MARTWY["10291"] = pomiar_dla(9.0, 14.0, "LOW", "Dane sprzed dni.", godzin_temu=72)
def z_martwym(url, naglowki=None, proby=None, zapasowy_ua=True):
    N["zapytania"] += 1
    for ident, odp in MARTWY.items():
        if ident in url:
            return odp
    raise siec.BladPobierania("nieobsłużony adres")
airly.pobierz_json = z_martwym
w = airly.pomiar()
etykiety = [p.tytul for p in w.pozycje]
print("   pokazane:", ", ".join(e[:30] for e in etykiety))
print("   uwaga:   ", w.status.uwaga)
assert w.status.ok, "pozostałe czujniki muszą działać dalej"
assert len(w.pozycje) == 4, "odczyt sprzed 72 h nie może trafić na stronę"
assert not any("Płośnica" in e for e in etykiety)
assert "4 z 5" in w.status.uwaga and "niedostępna" in w.status.uwaga

print("\n== brak znacznika czasu też dyskwalifikuje ==")
BEZ_CZASU = {"10298": {"current": {"values": [{"name": "PM25", "value": 10}],
                                   "indexes": [{"level": "LOW", "description": "x"}]}}}
def bez_czasu(url, naglowki=None, proby=None, zapasowy_ua=True):
    N["zapytania"] += 1
    return BEZ_CZASU["10298"]
airly.pobierz_json = bez_czasu
w = airly.pomiar()
print("   blad:", (w.status.blad or "")[:90])
assert not w.status.ok

airly.pobierz_json = fałszywy
print("\n== budżet dobowy ==")
from kolektor.konfiguracja import AIRLY_INSTALACJE, MIN_ODSTEP_MIN
NA_CYKL = len(AIRLY_INSTALACJE)
CYKL_MIN = ((MIN_ODSTEP_MIN["airly"] // 20) + 1) * 20      # workflow chodzi co 20 min
CYKLI = 24 * 60 // CYKL_MIN
print(f"   {NA_CYKL} czujników × {CYKLI} pobrań (cykl {CYKL_MIN} min) = "
      f"{NA_CYKL*CYKLI} zapytań na dobę, limit 100")
assert NA_CYKL * CYKLI <= 100, "konfiguracja przekracza dobowy limit Airly"

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
from kolektor.konfiguracja import AIRLY_INSTALACJE as _INST
assert len([p for p in dane["stany"] if p["zrodlo"] == "airly"]) == len(_INST), \
    "dane z pamięci muszą zostać przeniesione"

print("\nWszystkie kontrole przeszły.")
