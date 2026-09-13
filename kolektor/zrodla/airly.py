"""Airly – czujniki niskokosztowe w powiecie działdowskim.

W powiecie stoi 17 czujników opłaconych przez samorządy (Miasto Działdowo,
Gmina Działdowo, Iłowo-Osada, Płośnica, Rybno). Pokrycie jest więc znacznie
lepsze niż referencyjna stacja GIOŚ w Mławie — ale limit 100 zapytań na dobę
nie pozwala pobierać wszystkich.

Przyjęty kompromis: trzy czujniki o różnym charakterze terenu, odpytywane RAZ
NA GODZINĘ (kadencja w konfiguracji, nie tutaj). Stężenia pyłu zmieniają się
w skali godzin, więc częstsze pytanie nic nie wnosi, a ostrzeżenia pogodowe
odświeżają się dalej co 20 minut niezależnie od tego modułu.

Budżet: 3 zapytania × 24 cykle = 72 na dobę, 28 zostaje na błędy. Dlatego
proby=1 i wyłączony zapasowy User-Agent — nieudane żądania też wliczają się
do limitu.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from ..konfiguracja import (
    AIRLY_INSTALACJE, AIRLY_PROMIEN_KM, DLUGOSC, SZEROKOSC,
)
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..pomocnicze import jako_float, odleglosc_km
from ..siec import BladPobierania, pobierz_json

BAZA = "https://airapi.airly.eu/v2"
ZMIENNA_KLUCZA = "AIRLY_KLUCZ"

# Skala Airly CAQI przełożona na naszą 0–3.
POZIOMY = {
    "VERY_LOW": 0, "LOW": 0, "MEDIUM": 1,
    "HIGH": 2, "VERY_HIGH": 3, "EXTREME": 3, "AIRMAGEDDON": 3,
}


def _klucz() -> str | None:
    return (os.environ.get(ZMIENNA_KLUCZA, "") or "").strip() or None


def _naglowki(klucz: str) -> dict[str, str]:
    return {"apikey": klucz, "Accept": "application/json", "Accept-Language": "pl"}


def _pobierz(url: str, klucz: str) -> Any:
    return pobierz_json(url, _naglowki(klucz), proby=1, zapasowy_ua=False)


# Po ilu godzinach odczyt przestaje opisywać stan bieżący.
MAKS_WIEK_GODZIN = 3


def _swiezy(biezace: dict) -> tuple[bool, str]:
    """Czy pomiar jest aktualny.

    Czujnik Airly potrafi przestać działać, a API nadal zwraca strukturę
    z ostatnim znanym odczytem. Bez tej kontroli martwy czujnik pokazywałby
    dane sprzed dni jako stan bieżący — dokładnie ta cicha dezinformacja,
    której unikamy na poziomie źródeł.
    """
    znacznik = biezace.get("tillDateTime") or biezace.get("fromDateTime")
    if not znacznik:
        return False, "odpowiedź bez znacznika czasu"

    try:
        czas = datetime.fromisoformat(str(znacznik).replace("Z", "+00:00"))
    except ValueError:
        return False, f"nieczytelny znacznik czasu: {znacznik}"

    if czas.tzinfo is None:
        czas = czas.replace(tzinfo=teraz().tzinfo)

    godziny = (teraz() - czas).total_seconds() / 3600
    if godziny > MAKS_WIEK_GODZIN:
        return False, f"ostatni odczyt sprzed {godziny:.0f} h (czujnik nie działa?)"
    return True, ""


def _na_pozycje(dane: dict, etykieta: str) -> Pozycja | None:
    biezace = (dane or {}).get("current") or {}
    wartosci = {w.get("name"): w.get("value") for w in biezace.get("values") or []}
    indeksy = biezace.get("indexes") or []
    caqi = indeksy[0] if indeksy else {}

    pm25 = jako_float(wartosci.get("PM25"))
    pm10 = jako_float(wartosci.get("PM10"))

    # Wymagamy liczby, nie samego opisu. Airly dla zepsutego czujnika zwraca
    # strukturę z tekstem w rodzaju "Pracujemy nad tym, aby przywrócić ten
    # czujnik do pełnej sprawności" — bez wartości pomiarowych. Wcześniej
    # przechodziło to jako kafelka jakości powietrza bez żadnego pomiaru.
    if pm25 is None and pm10 is None:
        return None

    # Oba wskaźniki dokładnie zerowe to fizycznie niemożliwy odczyt,
    # w praktyce sygnał uszkodzonego czujnika.
    if (pm25 or 0) == 0 and (pm10 or 0) == 0:
        return None

    czesci = []
    if pm25 is not None:
        czesci.append(f"PM2,5: {pm25:.0f} µg/m³")
    if pm10 is not None:
        czesci.append(f"PM10: {pm10:.0f} µg/m³")

    opis = ", ".join(czesci)
    if caqi.get("description"):
        opis = f"{opis}. {caqi['description']}" if opis else str(caqi["description"])

    return Pozycja(
        zrodlo="airly",
        charakter="stan",
        typ="Jakość powietrza (czujnik lokalny)",
        tytul=etykieta,
        opis=opis,
        stopien=POZIOMY.get(str(caqi.get("level") or "").upper(), 0),
        dodatkowe={"pm25": pm25, "pm10": pm10, "caqi": jako_float(caqi.get("value"))},
    )


def pomiar() -> Wynik:
    status = StatusZrodla(id="airly", nazwa="Airly – czujniki lokalne")

    klucz = _klucz()
    if not klucz:
        status.uwaga = f"nieaktywne: brak {ZMIENNA_KLUCZA}"
        return Wynik(status=status)
    if not AIRLY_INSTALACJE:
        status.blad = "puste AIRLY_INSTALACJE — uruchom: python -m kolektor.main --airly"
        return Wynik(status=status)

    pozycje: list[Pozycja] = []
    bledy: list[str] = []

    for identyfikator, etykieta in AIRLY_INSTALACJE:
        url = f"{BAZA}/measurements/installation?installationId={identyfikator}"
        try:
            dane = _pobierz(url, klucz)
        except BladPobierania as e:
            bledy.append(f"{etykieta}: {e}")
            continue
        swiezy, powod = _swiezy((dane or {}).get("current") or {})
        if not swiezy:
            bledy.append(f"{etykieta}: {powod}")
            continue

        pozycja = _na_pozycje(dane, etykieta)
        if pozycja:
            pozycje.append(pozycja)
        else:
            bledy.append(f"{etykieta}: odpowiedź bez danych pomiarowych")

    if not pozycje:
        status.blad = " | ".join(bledy)[:300] or "brak danych ze wszystkich czujników"
        return Wynik(status=status)

    # Najgorszy odczyt na wierzchu — to on decyduje o kolorze i uwadze.
    pozycje.sort(key=lambda p: -p.stopien)

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"czujniki niskokosztowe (nie referencyjne), {len(pozycje)} z {len(AIRLY_INSTALACJE)}"
    if bledy:
        status.uwaga += " — część niedostępna"
    return Wynik(status=status, pozycje=pozycje)


# --- tryb diagnostyczny ------------------------------------------------

def instalacje_w_okolicy() -> list[dict[str, Any]]:
    """Lista instalacji z odległościami. Jedno zapytanie."""
    klucz = _klucz()
    if not klucz:
        raise BladPobierania(f"brak zmiennej środowiskowej {ZMIENNA_KLUCZA}")

    url = (
        f"{BAZA}/installations/nearest?lat={SZEROKOSC}&lng={DLUGOSC}"
        f"&maxDistanceKM={AIRLY_PROMIEN_KM}&maxResults=50"
    )
    dane = _pobierz(url, klucz)
    if not isinstance(dane, list):
        return []

    wynik = []
    for wpis in dane:
        polozenie = wpis.get("location") or {}
        lat = jako_float(polozenie.get("latitude"))
        lng = jako_float(polozenie.get("longitude"))
        adres = wpis.get("address") or {}
        wynik.append({
            "id": wpis.get("id"),
            "miejscowosc": adres.get("city") or "?",
            "ulica": adres.get("street") or "",
            "sponsor": (wpis.get("sponsor") or {}).get("displayName") or "",
            "km": round(odleglosc_km(SZEROKOSC, DLUGOSC, lat, lng), 1)
            if lat is not None and lng is not None else None,
        })
    wynik.sort(key=lambda w: (w["km"] is None, w["km"]))
    return wynik


def sprawdz_tryb_zbiorczy() -> str:
    """Czy measurements/nearest zwraca pomiary z wielu instalacji naraz.

    Jeśli tak, wszystkie 17 czujników dałoby się pobrać jednym zapytaniem
    i kadencję można by zostawić na 20 minutach. Sprawdzamy to ręcznie,
    jednym zapytaniem, zamiast marnować limit na próbę w każdym cyklu.
    """
    klucz = _klucz()
    if not klucz:
        return f"brak {ZMIENNA_KLUCZA}"

    url = (
        f"{BAZA}/measurements/nearest?lat={SZEROKOSC}&lng={DLUGOSC}"
        f"&maxDistanceKM={AIRLY_PROMIEN_KM}&maxResults=5"
    )
    try:
        dane = _pobierz(url, klucz)
    except BladPobierania as e:
        return f"endpoint odrzucił żądanie: {e}"

    if isinstance(dane, list):
        return (f"TRYB ZBIORCZY DOSTĘPNY — zwrócono listę {len(dane)} pomiarów "
                "w jednym zapytaniu. Warto przejść na ten tryb.")
    if isinstance(dane, dict) and "current" in dane:
        return ("tryb pojedynczy — endpoint zwraca jeden pomiar, "
                "parametr maxResults jest ignorowany. Zostajemy przy trzech czujnikach.")
    return f"nieznany kształt odpowiedzi: {type(dane).__name__}"
