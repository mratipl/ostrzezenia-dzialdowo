"""Stopień zagrożenia pożarowego lasu.

Jednostki Lasów Państwowych ustalają stopień w skali 0–3 dla stref
prognostycznych, na podstawie pomiarów o 9:00 i 13:00, w sezonie od 1 marca
do 30 września. Powiat działdowski leży w strefie RDLP Olsztyn
(nadleśnictwa Lidzbark i Dwukoły).

Poza sezonem źródło melduje to wprost jako uwagę, a nie jako błąd — inaczej
od października do lutego strona pokazywałaby stale czerwoną kafelkę.
"""

from __future__ import annotations

import re

from ..konfiguracja import LASY_STREFA
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania
from .html_pomoc import czysty, zupa

ADRESY = [
    "https://bazapozarow.ibles.pl/zagrozenie/",
    "https://www.traxelektronik.pl/pogoda/las/zbiorcza.php",
]

OPISY = {
    0: "brak zagrożenia",
    1: "małe zagrożenie",
    2: "duże zagrożenie",
    3: "katastrofalne zagrożenie",
}


def _w_sezonie() -> bool:
    return 3 <= teraz().month <= 9


def zagrozenie_pozarowe() -> Wynik:
    status = StatusZrodla(id="lasy", nazwa="Zagrożenie pożarowe lasu")

    if not _w_sezonie():
        status.ok = True
        status.pobrano = teraz().isoformat(timespec="seconds")
        status.uwaga = "poza sezonem (stopnie ustalane od 1 marca do 30 września)"
        return Wynik(status=status)

    tekst = ""
    bledy = []
    for url in ADRESY:
        try:
            tekst = czysty(zupa(url).get_text(" "))
            break
        except BladPobierania as e:
            bledy.append(str(e))

    if not tekst:
        status.blad = " ;; ".join(bledy)[:400]
        return Wynik(status=status)

    # Szukamy nazwy strefy i najbliższej jej cyfry 0-3.
    wzor = re.compile(rf"{re.escape(LASY_STREFA)}\D{{0,80}}?([0-3])", re.IGNORECASE)
    dopasowanie = wzor.search(tekst)

    if not dopasowanie:
        status.blad = (f"strona pobrana, nie znaleziono strefy '{LASY_STREFA}' "
                       "— sprawdź nazwę w LASY_STREFA")
        return Wynik(status=status)

    stopien = int(dopasowanie.group(1))

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    return Wynik(status=status, pozycje=[Pozycja(
        zrodlo="lasy",
        charakter="stan",
        typ="Zagrożenie pożarowe lasu",
        tytul=f"{LASY_STREFA}: {stopien}. stopień — {OPISY[stopien]}",
        opis=("Przy trzecim stopniu i utrzymującej się niskiej wilgotności ściółki "
              "nadleśnictwa mogą wprowadzić zakaz wstępu do lasu."
              if stopien >= 2 else
              "Stopień ustalany codziennie na podstawie pomiarów o 9:00 i 13:00."),
        stopien=stopien,
    )])
