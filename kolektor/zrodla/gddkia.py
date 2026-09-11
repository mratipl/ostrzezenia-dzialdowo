"""GDDKiA – utrudnienia na drogach krajowych (plik XML, bez rejestracji).

Uwaga: GDDKiA przenosiła serwis na drogi.gddkia.gov.pl i adres pliku bywał
zmieniany. Próbujemy kilku wariantów po kolei; jeśli żaden nie odpowie,
źródło melduje błąd zamiast po cichu pokazać pustą listę.

Ograniczenie merytoryczne: to wyłącznie drogi krajowe. Dróg wojewódzkich
i powiatowych nie ma tu i nie będzie.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..konfiguracja import FILTR_DROGOWY
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania, pobierz_tekst

ADRESY = [
    "https://www.gddkia.gov.pl/dane/zima_html/utrdane.xml",
    "https://www.gddkia.gov.pl/dane/utrudnienia/utrdane.xml",
]


def _tekst_wezla(wezel: ET.Element) -> str:
    return " ".join(t.strip() for t in wezel.itertext() if t and t.strip())


def _pasuje(tekst: str) -> bool:
    maly = tekst.lower()
    return any(fraza.lower() in maly for fraza in FILTR_DROGOWY)


def utrudnienia() -> Wynik:
    status = StatusZrodla(id="gddkia", nazwa="GDDKiA – drogi krajowe")

    surowe = None
    bledy = []
    for adres in ADRESY:
        try:
            surowe = pobierz_tekst(adres, {"Accept": "application/xml"})
            break
        except BladPobierania as e:
            bledy.append(str(e))

    if surowe is None:
        status.blad = "; ".join(bledy)[:300]
        return Wynik(status=status)

    try:
        korzen = ET.fromstring(surowe)
    except ET.ParseError as e:
        status.blad = f"Nieprawidłowy XML: {e}"
        return Wynik(status=status)

    pozycje: list[Pozycja] = []
    for wezel in korzen.iter():
        # Interesują nas węzły pojedynczego utrudnienia, czyli takie, których
        # dzieci są już liśćmi. Bez tego warunku korzeń dokumentu zlepiłby
        # treść wszystkich wpisów w jeden i przepuścił zdarzenia spoza terenu.
        if len(wezel) == 0 or any(len(dziecko) > 0 for dziecko in wezel):
            continue
        tresc = _tekst_wezla(wezel)
        if len(tresc) < 20 or not _pasuje(tresc):
            continue
        if any(tresc == p.opis for p in pozycje):
            continue
        pozycje.append(
            Pozycja(
                zrodlo="gddkia",
                charakter="zdarzenie",
                typ="Utrudnienie drogowe",
                tytul="Droga krajowa",
                opis=tresc[:400],
                stopien=1,
            )
        )
        if len(pozycje) >= 20:
            break

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    return Wynik(status=status, pozycje=pozycje)
