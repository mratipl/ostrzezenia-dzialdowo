"""GIOŚ – indeks jakości powietrza z najbliższej stacji.

W powiecie działdowskim nie ma stacji pomiarowej. Najbliższa jest w Mławie,
około 17 km od Działdowa. Odczyt z niej jest lepszy niż nic, ale nie opisuje
lokalnego zadymienia z palenisk domowych — dlatego odległość podajemy wprost
w tytule kafelki, żeby nikt nie odczytał tego jako pomiaru u siebie.

Endpoint zwracał HTTP 406, a zamiana User-Agenta nie pomogła. Zamiast zgadywać
nagłówek po jednym na przebieg, próbujemy kilku wariantów i zapisujemy w polu
uwaga, który zadziałał. Diagnostyka na produkcji zamiast w ciemno.
"""

from __future__ import annotations

from typing import Any

from ..konfiguracja import DLUGOSC, MAKS_STACJI, PROMIEN_STACJI_KM, SZEROKOSC
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..pomocnicze import jako_float, odleglosc_km, pierwsza_lista, pole, znormalizuj
from ..siec import BladPobierania, pobierz_json

BAZA = "https://api.gios.gov.pl/pjp-api"
URL_INDEKS = f"{BAZA}/v1/rest/aqindex/getIndex/{{}}"

# Kolejne próby dotarcia do listy stacji. Pierwsza, która zwróci dane, wygrywa.
WARIANTY: list[tuple[str, str, dict[str, str]]] = [
    ("v1 z paginacją", f"{BAZA}/v1/rest/station/findAll?page=0&size=500",
     {"Accept": "application/json"}),
    ("v1 bez parametrów", f"{BAZA}/v1/rest/station/findAll",
     {"Accept": "application/json"}),
    ("v1 z nagłówkami przeglądarki", f"{BAZA}/v1/rest/station/findAll?page=0&size=500",
     {"Accept": "application/json, text/plain, */*",
      "Accept-Language": "pl-PL,pl;q=0.9",
      "Referer": "https://powietrze.gios.gov.pl/"}),
    ("v1 bez nagłówka Accept", f"{BAZA}/v1/rest/station/findAll?page=0&size=500",
     {"Accept": "*/*"}),
    ("starsze API", f"{BAZA}/rest/station/findAll",
     {"Accept": "application/json"}),
]

SKALA = {
    "bardzodobry": 0, "dobry": 0, "umiarkowany": 1,
    "dostateczny": 2, "zly": 3, "bardzozly": 3,
}


def _wspolrzedne(wpis: dict) -> tuple[float, float] | None:
    """Para (szerokość, długość) wyłuskana po zakresie wartości dla Polski.

    Warunek części ułamkowej jest istotny: identyfikator stacji o wartości 52
    też mieści się w zakresie szerokości, a współrzędna nigdy nie jest całkowita.
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
    if isinstance(dane, dict) and len(dane) == 1:
        wnetrze = next(iter(dane.values()))
        if isinstance(wnetrze, dict):
            return wnetrze
    return dane if isinstance(dane, dict) else {}


def _lista_stacji() -> tuple[list, str, list[str]]:
    """Zwraca (stacje, nazwa udanego wariantu, komunikaty błędów)."""
    bledy: list[str] = []
    for opis, url, naglowki in WARIANTY:
        try:
            stacje = pierwsza_lista(pobierz_json(url, naglowki, proby=1))
        except BladPobierania as e:
            bledy.append(f"{opis}: {e}")
            continue
        if stacje:
            return stacje, opis, bledy
        bledy.append(f"{opis}: odpowiedź bez listy stacji")
    return [], "", bledy


def jakosc_powietrza() -> Wynik:
    status = StatusZrodla(id="gios", nazwa="GIOŚ – jakość powietrza")

    stacje, wariant, bledy = _lista_stacji()
    if not stacje:
        status.blad = " | ".join(bledy)[:400]
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

    if not blisko:
        status.blad = f"Brak stacji w promieniu {PROMIEN_STACJI_KM} km (wariant: {wariant})"
        return Wynik(status=status)

    pozycje: list[Pozycja] = []
    for dystans, stacja in blisko:
        ident = pole(stacja, "identyfikator stacji", "id", "stationId")
        if ident is None:
            continue
        try:
            indeks = _rozpakuj(pobierz_json(URL_INDEKS.format(ident), proby=1))
        except BladPobierania:
            continue

        kategoria = pole(indeks, "nazwa kategorii indeksu", "indexLevelName")
        if not kategoria:
            continue

        nazwa = str(pole(stacja, "nazwa stacji", "stationName", "nazwa", domyslnie="stacja"))
        pozycje.append(
            Pozycja(
                zrodlo="gios",
                charakter="stan",
                typ="Jakość powietrza (stacja referencyjna)",
                tytul=f"{nazwa} — {kategoria}",
                opis=(
                    f"Najbliższa stacja GIOŚ, około {dystans:.0f} km od Działdowa. "
                    "W powiecie nie ma stanowiska pomiarowego, więc odczyt nie "
                    "odzwierciedla lokalnego zadymienia z palenisk domowych."
                ),
                stopien=SKALA.get(znormalizuj(str(kategoria)), 0),
                dodatkowe={"odleglosc_km": round(dystans), "stacja": nazwa},
            )
        )

    if not pozycje:
        status.blad = f"Stacje znalezione, żadna nie zwróciła indeksu (wariant: {wariant})"
        return Wynik(status=status)

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"wariant zapytania: {wariant}"
    return Wynik(status=status, pozycje=pozycje)
