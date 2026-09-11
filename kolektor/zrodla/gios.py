"""GIOŚ – indeks jakości powietrza (API v1).

Stare endpointy pjp-api/rest/... zostały wycofane; używamy wersji v1.
Klucze w odpowiedziach są po polsku, ze spacjami i znakami spoza ASCII,
więc współrzędne wyłuskujemy po zakresie wartości, a nie po nazwie pola —
to znacznie odporniejsze niż zgadywanie, jak dziś nazywa się kolumna.
"""

from __future__ import annotations

from typing import Any

from ..konfiguracja import (
    DLUGOSC, MAKS_STACJI, PROMIEN_STACJI_KM, SZEROKOSC,
)
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..pomocnicze import jako_float, odleglosc_km, pierwsza_lista, pole, znormalizuj
from ..siec import BladPobierania, pobierz_json

BAZA = "https://api.gios.gov.pl/pjp-api/v1/rest"
URL_STACJE = f"{BAZA}/station/findAll?page=0&size=500"
URL_INDEKS = f"{BAZA}/aqindex/getIndex/{{}}"

# Skala GIOŚ przełożona na naszą skalę 0–3.
SKALA = {
    "bardzodobry": 0,
    "dobry": 0,
    "umiarkowany": 1,
    "dostateczny": 2,
    "zly": 3,
    "bardzozly": 3,
}


def _wspolrzedne(wpis: dict) -> tuple[float, float] | None:
    """Szuka pary (szerokość, długość) po wiarygodnym zakresie dla Polski.

    Warunek części ułamkowej jest istotny: identyfikator stacji o wartości 52
    też mieści się w zakresie szerokości geograficznej, a współrzędna nigdy
    nie jest liczbą całkowitą.
    """
    szerokosc = dlugosc = None
    for wartosc in wpis.values():
        if isinstance(wartosc, bool):
            continue
        liczba = jako_float(wartosc)
        if liczba is None or float(liczba).is_integer():
            continue
        if szerokosc is None and 48.0 <= liczba <= 56.0:
            szerokosc = liczba
        if dlugosc is None and 13.0 <= liczba <= 25.0:
            dlugosc = liczba
    if szerokosc is not None and dlugosc is not None:
        return szerokosc, dlugosc
    return None


def _rozpakuj(dane: Any) -> dict:
    """Odpowiedzi v1 bywają opakowane w jednoklucowy obiekt."""
    if isinstance(dane, dict) and len(dane) == 1:
        wnetrze = next(iter(dane.values()))
        if isinstance(wnetrze, dict):
            return wnetrze
    return dane if isinstance(dane, dict) else {}


def _identyfikator(wpis: dict) -> Any:
    return pole(wpis, "identyfikator stacji", "id", "stationId")


def _nazwa_stacji(wpis: dict) -> str:
    return str(pole(wpis, "nazwa stacji", "stationName", "nazwa", domyslnie="stacja"))


def jakosc_powietrza() -> Wynik:
    status = StatusZrodla(id="gios", nazwa="GIOŚ – jakość powietrza")
    try:
        stacje = pierwsza_lista(pobierz_json(URL_STACJE))
    except BladPobierania as e:
        status.blad = str(e)
        return Wynik(status=status)

    blisko: list[tuple[float, dict]] = []
    for stacja in stacje:
        if not isinstance(stacja, dict):
            continue
        wsp = _wspolrzedne(stacja)
        if not wsp:
            continue
        dystans = odleglosc_km(SZEROKOSC, DLUGOSC, wsp[0], wsp[1])
        if dystans <= PROMIEN_STACJI_KM:
            blisko.append((dystans, stacja))

    blisko.sort(key=lambda p: p[0])
    blisko = blisko[:MAKS_STACJI]

    pozycje: list[Pozycja] = []
    udane = 0
    for dystans, stacja in blisko:
        ident = _identyfikator(stacja)
        if ident is None:
            continue
        try:
            indeks = _rozpakuj(pobierz_json(URL_INDEKS.format(ident)))
        except BladPobierania:
            continue

        kategoria = pole(indeks, "nazwa kategorii indeksu", "indexLevelName")
        if not kategoria:
            continue
        udane += 1

        pozycje.append(
            Pozycja(
                zrodlo="gios",
                charakter="stan",
                typ="Jakość powietrza",
                tytul=f"{_nazwa_stacji(stacja)} — {kategoria}",
                opis=f"Stacja pomiarowa w odległości około {dystans:.0f} km.",
                stopien=SKALA.get(znormalizuj(str(kategoria)), 0),
                dodatkowe={"odleglosc_km": round(dystans)},
            )
        )

    if not blisko:
        status.blad = f"Brak stacji GIOŚ w promieniu {PROMIEN_STACJI_KM} km"
        return Wynik(status=status)
    if udane == 0:
        status.blad = "Stacje znalezione, ale żadna nie zwróciła indeksu"
        return Wynik(status=status)

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    return Wynik(status=status, pozycje=pozycje)
