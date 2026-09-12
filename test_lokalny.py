"""Test na danych zastępczych — sprawdza kolektor bez dostępu do sieci.

Uruchom: python3 test_lokalny.py
Nie zastępuje testu na żywych danych (patrz --zrzut), ale wyłapuje błędy
w logice filtrowania, świeżości i renderowania.
"""

import json
from kolektor import siec

METEO = [
    {
        "id": "M-001", "nazwa_zdarzenia": "Silny wiatr", "stopien": "2",
        "prawdopodobienstwo": "80",
        "obowiazuje_od": "2026-09-11T18:00:00", "obowiazuje_do": "2026-09-12T06:00:00",
        "tresc": "Prognozuje się wystąpienie silnego wiatru o średniej prędkości do 45 km/h, "
                 "z porywami do 100 km/h, z zachodu.",
        "biuro": "Biuro Prognoz Meteorologicznych w Gdyni",
        "teryt": ["2803", "2861", "2862"],
    },
    {
        "id": "M-002", "nazwa_zdarzenia": "Upał", "stopien": "1",
        "obowiazuje_od": "2026-09-11T12:00:00", "obowiazuje_do": "2026-09-11T20:00:00",
        "tresc": "Prognozuje się temperaturę maksymalną do 31°C.",
        "teryt": ["1261", "1262"],
    },
]

HYDRO = [
    {
        "id": "H-77", "zjawisko": "Wezbranie z przekroczeniem stanów ostrzegawczych",
        "stopien": "1", "prawdopodobienstwo": "70",
        "obowiazuje_od": "2026-09-11T10:00:00", "obowiazuje_do": "2026-09-13T10:00:00",
        "opis": "Wkra — wzrosty stanów wody w strefie stanów ostrzegawczych.",
        "teryt": ["2803011", "2803022"],
    }
]

STACJE = {"Lista stacji pomiarowych": [
    {"Identyfikator stacji": 9153, "Nazwa stacji": "Olsztyn, ul. Puszkina",
     "WGS84 φ N": "53.788", "WGS84 λ E": "20.486"},
    {"Identyfikator stacji": 52, "Nazwa stacji": "Warszawa-Ursynów",
     "WGS84 φ N": "52.160", "WGS84 λ E": "21.034"},
    {"Identyfikator stacji": 8899, "Nazwa stacji": "Mława, ul. Sienkiewicza",
     "WGS84 φ N": "53.113", "WGS84 λ E": "20.383"},
]}

INDEKS = {"AqIndex": {
    "Identyfikator stacji pomiarowej": 9153,
    "Nazwa kategorii indeksu": "Dobry",
    "Data wykonania obliczeń indeksu": "2026-09-11 09:00:00",
}}

POGODA = {"hourly": {
    "wind_gusts_10m": [45 + i for i in range(24)],
    "precipitation": [0.2] * 24,
    "temperature_2m": [12 + (i % 9) for i in range(24)],
}}

XML = """<?xml version="1.0" encoding="UTF-8"?>
<utrudnienia>
  <utrudnienie><droga>DK15</droga><wojewodztwo>warmińsko-mazurskie</wojewodztwo>
    <opis>Roboty drogowe, ruch wahadłowy na odcinku w okolicy Lidzbarka.</opis></utrudnienie>
  <utrudnienie><droga>A4</droga><wojewodztwo>dolnośląskie</wojewodztwo>
    <opis>Zdarzenie drogowe, zablokowany prawy pas ruchu w kierunku Wrocławia.</opis></utrudnienie>
</utrudnienia>"""


def fałszywy_json(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "warningsmeteo" in url:
        return METEO
    if "warningshydro" in url:
        return HYDRO
    if "station/findAll" in url:
        return STACJE
    if "aqindex" in url:
        return INDEKS
    if "open-meteo" in url:
        return POGODA
    raise siec.BladPobierania(f"nieobsłużony adres: {url}")


def fałszywy_tekst(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "utrdane" in url:
        return XML
    raise siec.BladPobierania(f"nieobsłużony adres: {url}")


siec.pobierz_json = fałszywy_json
siec.pobierz_tekst = fałszywy_tekst
for modul in ("imgw", "gios", "open_meteo", "gddkia", "airly"):
    m = __import__(f"kolektor.zrodla.{modul}", fromlist=["x"])
    if hasattr(m, "pobierz_json"):
        m.pobierz_json = fałszywy_json
    if hasattr(m, "pobierz_tekst"):
        m.pobierz_tekst = fałszywy_tekst

from kolektor.main import zbierz, WYJSCIE  # noqa: E402

zbierz()

dane = json.loads((WYJSCIE / "dane.json").read_text(encoding="utf-8"))

print("\n--- kontrola ---")
print("nagłówek:          ", dane["naglowek"])
print("najwyższy stopień: ", dane["najwyzszy_stopien"])
print("zdarzeń:           ", len(dane["zdarzenia"]))
print("stanów:            ", len(dane["stany"]))
print("niedostępne:       ", dane["zrodla_niedostepne"] or "brak")

tytuly = [z["tytul"] for z in dane["zdarzenia"]]
assert "Silny wiatr" in tytuly, "zgubiono ostrzeżenie dla TERYT 2803"
assert "Upał" not in tytuly, "przepuszczono ostrzeżenie spoza powiatu"
assert any("Wezbranie" in t for t in tytuly), "zgubiono ostrzeżenie hydrologiczne"
assert dane["najwyzszy_stopien"] == 2
assert any("Olsztyn" in s["tytul"] or "Mława" in s["tytul"] for s in dane["stany"])
assert not any("Warszawa" in s["tytul"] for s in dane["stany"]), "stacja spoza promienia"
from kolektor.konfiguracja import ZRODLA_WYLACZONE
if "gddkia" in ZRODLA_WYLACZONE:
    assert not any(z["zrodlo"] == "gddkia" for z in dane["zdarzenia"]), "wyłączone źródło nadal widoczne"
    assert not any(z["id"] == "gddkia" for z in dane["zrodla"]), "wyłączone źródło w tabeli"
else:
    assert any("Lidzbark" in z["opis"] for z in dane["zdarzenia"]), "zgubiono utrudnienie"
    assert not any("Wrocławia" in z["opis"] for z in dane["zdarzenia"]), "utrudnienie spoza terenu"
PODSTAWIONE = {"IMGW", "GIOŚ", "Open-Meteo"}
zepsute = [z["nazwa"] for z in dane["zrodla"]
           if not z["ok"] and any(n in z["nazwa"] for n in PODSTAWIONE)]
assert not zepsute, f"źródła zastępcze powinny działać: {zepsute}"
print("\nWszystkie kontrole przeszły.")
