"""Tolerancyjne czytanie pól.

API IMGW i GIOŚ nie mają opublikowanego schematu odpowiedzi, a GIOŚ dodatkowo
używa polskich nazw kluczy ze spacjami. Zamiast zakładać konkretne nazwy,
szukamy pola po kilku kandydatach i po fragmencie nazwy. Dzięki temu drobna
zmiana po stronie dostawcy nie wywraca kolektora.
"""

from __future__ import annotations

import math
import unicodedata
from typing import Any


def znormalizuj(tekst: str) -> str:
    """małe litery, bez ogonków, bez separatorów — do porównywania nazw kluczy"""
    bez_ogonkow = unicodedata.normalize("NFKD", tekst)
    bez_ogonkow = "".join(z for z in bez_ogonkow if not unicodedata.combining(z))
    return "".join(z for z in bez_ogonkow.lower() if z.isalnum())


def bez_ogonkow(tekst: str) -> str:
    """Małe litery bez znaków diakrytycznych, ze zachowaniem spacji.

    W przeciwieństwie do znormalizuj() nie usuwa separatorów, więc nadaje się
    do dopasowywania fraz wielowyrazowych. Potrzebne, bo część serwisów pisze
    bez polskich znaków ("ostrzezenie", "wylaczenie pradu") i dopasowanie
    po formie z ogonkami po prostu nie trafia.
    """
    rozlozone = unicodedata.normalize("NFKD", tekst or "")
    return "".join(z for z in rozlozone if not unicodedata.combining(z)).lower()


def pole(slownik: dict[str, Any], *kandydaci: str, domyslnie: Any = None) -> Any:
    """Zwraca pierwszą pasującą wartość. Najpierw trafienie dokładne, potem po fragmencie."""
    if not isinstance(slownik, dict):
        return domyslnie

    mapa = {znormalizuj(str(k)): v for k, v in slownik.items()}

    for kandydat in kandydaci:
        klucz = znormalizuj(kandydat)
        if klucz in mapa and mapa[klucz] not in (None, ""):
            return mapa[klucz]

    for kandydat in kandydaci:
        klucz = znormalizuj(kandydat)
        for nazwa, wartosc in mapa.items():
            if klucz and klucz in nazwa and wartosc not in (None, ""):
                return wartosc

    return domyslnie


def pole_w_glab(obiekt: Any, *kandydaci: str, glebokosc: int = 4) -> Any:
    """Szuka pola rekurencyjnie, nie tylko na wierzchu struktury.

    Potrzebne, bo GIOŚ zagnieżdża kategorię indeksu w podobiekcie
    (np. stIndexLevel.indexLevelName), a poziom zagnieżdżenia zmieniał się
    między wersjami API.
    """
    if glebokosc < 0:
        return None

    trafienie = pole(obiekt, *kandydaci) if isinstance(obiekt, dict) else None
    if trafienie not in (None, "") and not isinstance(trafienie, (dict, list)):
        return trafienie

    dzieci = obiekt.values() if isinstance(obiekt, dict) else (
        obiekt if isinstance(obiekt, (list, tuple)) else ())
    for dziecko in dzieci:
        if isinstance(dziecko, (dict, list, tuple)):
            wynik = pole_w_glab(dziecko, *kandydaci, glebokosc=glebokosc - 1)
            if wynik not in (None, ""):
                return wynik
    return None


def pierwsza_lista(dane: Any) -> list:
    """GIOŚ pakuje wyniki w obiekt z polską nazwą klucza. Wyciągamy pierwszą listę."""
    if isinstance(dane, list):
        return dane
    if isinstance(dane, dict):
        for wartosc in dane.values():
            if isinstance(wartosc, list):
                return wartosc
    return []


def zawiera_teryt(obiekt: Any, prefiks: str) -> bool:
    """Czy gdziekolwiek w strukturze jest kod TERYT zaczynający się od prefiksu.

    Działa i dla kodów powiatu (2803), i dla kodów gmin (2803011, 2803022...),
    niezależnie od tego, czy IMGW zwraca je jako listę, string czy zagnieżdżony obiekt.
    """
    if isinstance(obiekt, str):
        oczyszczony = obiekt.strip()
        return oczyszczony.isdigit() and oczyszczony.startswith(prefiks)
    if isinstance(obiekt, (int,)):
        return str(obiekt).startswith(prefiks)
    if isinstance(obiekt, dict):
        return any(zawiera_teryt(w, prefiks) for w in obiekt.values())
    if isinstance(obiekt, (list, tuple)):
        return any(zawiera_teryt(w, prefiks) for w in obiekt)
    return False


def odleglosc_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine — do szukania najbliższych stacji pomiarowych."""
    r = 6371.0
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def jako_float(wartosc: Any) -> float | None:
    if wartosc in (None, ""):
        return None
    try:
        return float(str(wartosc).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
