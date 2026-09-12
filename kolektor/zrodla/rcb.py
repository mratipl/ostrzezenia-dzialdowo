"""RCB – komunikaty oraz obowiązujące stopnie alarmowe.

Brak API, więc parsujemy gov.pl/web/rcb. Dwa różne zadania:

- komunikaty to ZDARZENIA: mają czas, wygasają, filtrujemy po terenie
- stopnie alarmowe to STAN: obowiązują do odwołania i nie mogą migać

Stopnie wyciągamy wyrażeniem regularnym z całego tekstu strony, nie ze
struktury DOM. To celowe: układ strony zmienia się przy każdym odświeżeniu
serwisu, a słowa BRAVO, CHARLIE i CRP nie zmieniają się od lat.

Przypomnienie merytoryczne: stopnie alarmowe wprowadza Prezes Rady Ministrów
w drodze zarządzenia (art. 16 ust. 1 pkt 1 ustawy o działaniach
antyterrorystycznych), a nie Rada Ministrów.
"""

from __future__ import annotations

import re
from datetime import timedelta

from ..konfiguracja import FRAZY_TERENU
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania
from .html_pomoc import (
    czysty, data_po_frazie, data_z_tekstu, dotyczy_terenu, pelny_adres,
    wpisy_z_listy, zupa,
)

URL_KOMUNIKATY = "https://www.gov.pl/web/rcb/komunikaty"

# Adresy, pod którymi RCB publikuje informację o stopniach. Pierwszy działający wygrywa.
URL_STOPNIE = [
    "https://www.gov.pl/web/rcb/stopnie-alarmowe",
    "https://www.gov.pl/web/rcb/komunikaty",
    "https://www.gov.pl/web/premier/stopnie-alarmowe",
]

NAZWY_STOPNI = ["ALFA", "BRAVO", "CHARLIE", "DELTA"]

# Stopień alarmowy sam w sobie nie jest zagrożeniem bieżącym — to stan
# podwyższonej czujności. Kolor dobieramy powściągliwie, żeby nie zagłuszał
# realnych ostrzeżeń pogodowych.
WAGA = {"ALFA": 0, "BRAVO": 1, "CHARLIE": 2, "DELTA": 3}


def komunikaty() -> Wynik:
    status = StatusZrodla(id="rcb", nazwa="RCB – komunikaty")
    try:
        dokument = zupa(URL_KOMUNIKATY)
    except BladPobierania as e:
        status.blad = str(e)
        return Wynik(status=status)

    wpisy, strategia = wpisy_z_listy(dokument)
    if not wpisy:
        status.blad = "nie rozpoznano układu listy komunikatów (zmiana strony?)"
        return Wynik(status=status)

    granica = teraz() - timedelta(days=14)
    pozycje: list[Pozycja] = []

    for wpis in wpisy[:40]:
        tresc = f"{wpis['tytul']} {wpis['tekst']}"
        if not dotyczy_terenu(tresc, FRAZY_TERENU):
            continue

        data = data_z_tekstu(tresc)
        if data and data.replace(tzinfo=granica.tzinfo) < granica:
            continue          # komunikat starszy niż dwa tygodnie

        pozycje.append(Pozycja(
            zrodlo="rcb",
            charakter="zdarzenie",
            typ="Komunikat RCB",
            tytul=wpis["tytul"],
            opis=wpis["tekst"][:400],
            stopien=1,
            obowiazuje_od=data.isoformat() if data else None,
            link=pelny_adres(wpis["link"], URL_KOMUNIKATY),
        ))

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"układ listy: {strategia}, wpisów na stronie: {len(wpisy)}"
    return Wynik(status=status, pozycje=pozycje)


def _wytnij_stopnie(tekst: str) -> list[tuple[str, bool, str]]:
    """Zwraca listę (nazwa, czy_CRP, fragment kontekstu)."""
    znalezione: list[tuple[str, bool, str]] = []
    for nazwa in NAZWY_STOPNI:
        for dopasowanie in re.finditer(
            rf"\b{nazwa}(\s*[-–]\s*CRP)?\b", tekst, re.IGNORECASE
        ):
            crp = bool(dopasowanie.group(1))
            poczatek = max(0, dopasowanie.start() - 160)
            kontekst = czysty(tekst[poczatek:dopasowanie.end() + 220])
            znalezione.append((nazwa, crp, kontekst))
    return znalezione


def stopnie_alarmowe() -> Wynik:
    status = StatusZrodla(id="stopnie-alarmowe", nazwa="Stopnie alarmowe")

    tekst = ""
    bledy = []
    for url in URL_STOPNIE:
        try:
            tekst = czysty(zupa(url).get_text(" "))
        except BladPobierania as e:
            bledy.append(str(e))
            continue
        if any(n in tekst.upper() for n in NAZWY_STOPNI):
            break
        bledy.append(f"{url}: brak wzmianki o stopniach")
        tekst = ""

    if not tekst:
        status.blad = " ;; ".join(bledy)[:400]
        return Wynik(status=status)

    trafienia = _wytnij_stopnie(tekst)
    if not trafienia:
        status.blad = "strona pobrana, ale nie rozpoznano żadnego stopnia"
        return Wynik(status=status)

    # Deduplikacja po (nazwa, CRP) — ten sam stopień pojawia się na stronie wielokrotnie.
    najlepsze: dict[tuple[str, bool], str] = {}
    for nazwa, crp, kontekst in trafienia:
        klucz = (nazwa, crp)
        if klucz not in najlepsze or len(kontekst) > len(najlepsze[klucz]):
            najlepsze[klucz] = kontekst

    # Szukamy daty PO słowie "do", inaczej złapalibyśmy dzień wejścia w życie.
    do_kiedy = data_po_frazie(
        tekst, "obowiązują do", "obowiązuje do", "ważne do", " do ",
    )
    pozycje: list[Pozycja] = []

    for (nazwa, crp), kontekst in sorted(najlepsze.items(), key=lambda x: -WAGA[x[0][0]]):
        etykieta = f"{nazwa}-CRP" if crp else nazwa
        pozycje.append(Pozycja(
            zrodlo="stopnie-alarmowe",
            charakter="stan",
            typ="Stopień alarmowy",
            tytul=f"Obowiązuje stopień {etykieta}",
            opis=kontekst[:400],
            stopien=WAGA[nazwa],
            obowiazuje_do=do_kiedy.isoformat() if do_kiedy else None,
            link=URL_STOPNIE[0],
        ))

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    if do_kiedy:
        zostalo = (do_kiedy.date() - teraz().date()).days
        status.uwaga = f"termin ważności: {do_kiedy:%d.%m.%Y} (za {zostalo} dni)"
        if zostalo <= 14:
            status.uwaga += " — zbliża się przedłużenie, sprawdź własne dokumenty"
    return Wynik(status=status, pozycje=pozycje[:6])
