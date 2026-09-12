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

# Kolejność ma znaczenie: bazapozarow.ibles.pl/zagrozenie/ zwróciło 1180 znaków
# samego opisu metody IBL, bez danych — to strona wprowadzająca, właściwa mapa
# ładowana jest osobno. Dlatego najpierw tabela zbiorcza Traxa, a przyjmujemy
# tylko odpowiedź, w której faktycznie są dane stref.
ADRESY = [
    "https://www.traxelektronik.pl/pogoda/las/zbiorcza.php",
    "https://bazapozarow.ibles.pl/zagrozenie/mapa",
    "https://bazapozarow.ibles.pl/zagrozenie/",
]

# Bez któregoś z tych słów strona jest opisem, nie danymi — nie ma sensu
# szukać w niej stopnia.
SYGNALY_DANYCH = ["strefa", "nadleśnictwo", "nadlesnictwo", "rdlp", "stopień", "stopien"]
# Próg celowo niski: głównym filtrem są słowa kluczowe, nie długość.
# Strona wprowadzająca IBL miała 1180 znaków, ale nie zawierała ani nazwy
# strefy, ani słowa "stopień" — i to ją odrzuca, a nie rozmiar.
MIN_ZNAKOW = 600

OPISY = {
    0: "brak zagrożenia",
    1: "małe zagrożenie",
    2: "duże zagrożenie",
    3: "katastrofalne zagrożenie",
}


def _stopien_z_tabeli(dokument, nazwy: list[str]) -> tuple[int | None, str]:
    """Stopień z komórek tabeli — precyzyjniej niż wyrażenie regularne na tekście.

    Powód zmiany: w wierszu tabeli jest wiele liczb (numer strefy, wilgotność
    ściółki), a szukanie "pierwszej cyfry 0-3 po nazwie" trafiało w numer
    strefy zamiast w stopień. Tutaj wymagamy komórki, której CAŁA treść to
    jedna cyfra 0-3 — numer strefy siedzi w komórce z tekstem, stopień nie.
    """
    if dokument is None:
        return None, ""

    male = [n.lower() for n in nazwy]
    for wiersz in dokument.find_all("tr"):
        komorki = [czysty(k.get_text(" ")) for k in wiersz.find_all(["td", "th"])]
        if not komorki:
            continue
        polaczone = " ".join(komorki).lower()
        if not any(n in polaczone for n in male):
            continue
        for komorka in komorki:
            if re.fullmatch(r"[0-3]", komorka):
                return int(komorka), "komórka tabeli"
    return None, ""


def _stopien_z_tekstu(tekst: str, nazwy: list[str]) -> tuple[int | None, str]:
    """Rezerwa, gdy strona nie używa tabeli."""
    for nazwa in nazwy:
        m = re.search(
            rf"{re.escape(nazwa)}\D{{0,40}}?stopie\w*\D{{0,10}}?([0-3])\b",
            tekst, re.IGNORECASE,
        )
        if m:
            return int(m.group(1)), "tekst, przy słowie stopień"
    return None, ""


def _w_sezonie() -> bool:
    return 3 <= teraz().month <= 9


def zagrozenie_pozarowe() -> Wynik:
    status = StatusZrodla(id="lasy", nazwa="Zagrożenie pożarowe lasu")

    if not _w_sezonie():
        status.ok = True
        status.pobrano = teraz().isoformat(timespec="seconds")
        status.uwaga = "poza sezonem (stopnie ustalane od 1 marca do 30 września)"
        return Wynik(status=status)

    dokument = None
    tekst = ""
    zrodlo_tekstu = ""
    bledy = []
    for url in ADRESY:
        try:
            kandydat_dokument = zupa(url)
            kandydat = czysty(kandydat_dokument.get_text(" "))
        except BladPobierania as e:
            bledy.append(str(e))
            continue

        maly = kandydat.lower()
        brakujace = not any(s in maly for s in SYGNALY_DANYCH)
        if len(kandydat) < MIN_ZNAKOW:
            bledy.append(f"{url}: tylko {len(kandydat)} znaków (za mało na tabelę)")
            continue
        if brakujace:
            bledy.append(f"{url}: {len(kandydat)} znaków, ale bez słów {SYGNALY_DANYCH[:3]} "
                         "— to strona opisowa, nie dane")
            continue

        tekst, dokument, zrodlo_tekstu = kandydat, kandydat_dokument, url
        break

    if not tekst:
        status.blad = " ;; ".join(bledy)[:500]
        return Wynik(status=status)

    warianty_nazwy = [
        LASY_STREFA, f"RDLP {LASY_STREFA}", f"RDLP w {LASY_STREFA}ie",
        f"{LASY_STREFA}ie", "Lidzbark", "Dwukoły",
    ]

    stopien, skad = _stopien_z_tabeli(dokument, warianty_nazwy)

    if stopien is None:
        stopien, skad = _stopien_z_tekstu(tekst, warianty_nazwy)

    if stopien is None:
        probka = tekst[:300] if tekst else "(pusto)"
        status.blad = (
            f"strona pobrana ({len(tekst)} znaków), nie ustalono stopnia dla "
            f"{warianty_nazwy[:3]}. Początek treści: {probka}"
        )
        return Wynik(status=status)

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"źródło: {zrodlo_tekstu.split('/')[2]} ({skad})"
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
