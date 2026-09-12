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

    # Kilka wariantów zapisu nazwy strefy — serwisy LP używają różnych form.
    warianty_nazwy = [
        LASY_STREFA, f"RDLP {LASY_STREFA}", f"RDLP w {LASY_STREFA}ie",
        f"{LASY_STREFA}ie", "Lidzbark", "Dwukoły",
    ]
    dopasowanie = None
    for nazwa in warianty_nazwy:
        dopasowanie = re.search(
            rf"{re.escape(nazwa)}\D{{0,80}}?([0-3])\b", tekst, re.IGNORECASE
        )
        if dopasowanie:
            break

    if not dopasowanie:
        # Bez próbki tekstu kolejna iteracja byłaby znowu zgadywaniem.
        probka = tekst[:300] if tekst else "(pusto)"
        status.blad = (
            f"strona pobrana ({len(tekst)} znaków), nie znaleziono żadnego z wariantów "
            f"{warianty_nazwy[:3]}. Początek treści: {probka}"
        )
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
