"""Open-Meteo – prognoza na najbliższe 24 h. Bez klucza, bez rejestracji.

Traktujemy ją jako uzupełnienie, nie jako ostrzeżenie: formalnym źródłem
ostrzeżeń pozostaje IMGW. Stąd charakter "stan", nie "zdarzenie".
"""

from __future__ import annotations

from ..konfiguracja import DLUGOSC, SZEROKOSC
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania, pobierz_json

URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={SZEROKOSC}&longitude={DLUGOSC}"
    "&hourly=wind_gusts_10m,precipitation,temperature_2m"
    "&forecast_days=2&timezone=Europe%2FWarsaw"
)

# Progi orientacyjne, zbliżone do skali ostrzeżeń IMGW dla wiatru (km/h).
PROG_1 = 60
PROG_2 = 80
PROG_3 = 100


def prognoza() -> Wynik:
    status = StatusZrodla(id="open-meteo", nazwa="Open-Meteo – prognoza 24 h")
    try:
        dane = pobierz_json(URL)
    except BladPobierania as e:
        status.blad = str(e)
        return Wynik(status=status)

    godzinowe = dane.get("hourly") or {}
    porywy = [w for w in (godzinowe.get("wind_gusts_10m") or [])[:24] if w is not None]
    opady = [w for w in (godzinowe.get("precipitation") or [])[:24] if w is not None]
    temperatury = [w for w in (godzinowe.get("temperature_2m") or [])[:24] if w is not None]

    if not porywy:
        status.blad = "Odpowiedź bez danych godzinowych"
        return Wynik(status=status)

    maks_poryw = max(porywy)
    suma_opadow = round(sum(opady), 1) if opady else 0.0

    stopien = 0
    if maks_poryw >= PROG_3:
        stopien = 3
    elif maks_poryw >= PROG_2:
        stopien = 2
    elif maks_poryw >= PROG_1:
        stopien = 1

    opis = f"Najsilniejszy prognozowany poryw {maks_poryw:.0f} km/h, suma opadów {suma_opadow} mm."
    if temperatury:
        opis += f" Temperatura od {min(temperatury):.0f} do {max(temperatury):.0f} °C."

    pozycja = Pozycja(
        zrodlo="open-meteo",
        charakter="stan",
        typ="Prognoza",
        tytul="Najbliższe 24 godziny",
        opis=opis,
        stopien=stopien,
        dodatkowe={
            "maks_poryw_kmh": round(maks_poryw),
            "suma_opadow_mm": suma_opadow,
        },
    )

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    return Wynik(status=status, pozycje=[pozycja])
