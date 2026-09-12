"""Serwisy starostwa i gmin powiatu działdowskiego.

Powstało jako odpowiedź na realny problem: jednostki publikują najwięcej na
Facebooku, ale jego odczyt wymaga uprawnienia Page Public Content Access
(App Review i weryfikacja firmy), a scraping łamie regulamin i jest blokowany
dla adresów z centrów danych. Witryny urzędowe są dostępne legalnie i zawierają
to, co dla zarządzania kryzysowego istotne: awarie, przerwy w dostawie wody,
treningi syren, zakazy, utrudnienia.

Strategia na serwis: pobierz stronę główną, znajdź w niej ogłoszony kanał RSS
i użyj go, a gdy go nie ma — parsuj listę aktualności z HTML-a. Maksymalnie
dwa żądania na serwis, stąd kadencja godzinowa.

Każdy serwis ma osobny raport, więc awaria jednego nie gasi pozostałych, ale
liczba działających trafia do uwagi — użytkownik musi wiedzieć, że widzi
część obrazu, a nie całość.
"""

from __future__ import annotations

from datetime import timedelta

from ..konfiguracja import GMINY, GMINY_DNI_WSTECZ, SLOWA_KRYZYSOWE
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania, pobierz_tekst
from .html_pomoc import (
    PRZEGLADARKA, adres_rss, data_z_tekstu, dotyczy_terenu, pelny_adres,
    wpisy_z_listy, wpisy_z_rss, zupa,
)


def _wpisy_serwisu(url: str) -> tuple[list[dict], str]:
    """Zwraca (wpisy, opis użytej metody). Podnosi BladPobierania."""
    dokument = zupa(url, proby=1)

    kanal = adres_rss(dokument, url)
    if kanal:
        try:
            wpisy = wpisy_z_rss(pobierz_tekst(kanal, PRZEGLADARKA, proby=1))
        except BladPobierania:
            wpisy = []
        if wpisy:
            return wpisy, "RSS"

    wpisy, strategia = wpisy_z_listy(dokument)
    for wpis in wpisy:
        wpis.setdefault("data", data_z_tekstu(wpis.get("tekst", "")))
    return wpisy, f"HTML ({strategia})" if wpisy else ""


def komunikaty_gmin() -> Wynik:
    status = StatusZrodla(id="gminy", nazwa="Serwisy starostwa i gmin")

    granica = teraz() - timedelta(days=GMINY_DNI_WSTECZ)
    pozycje: list[Pozycja] = []
    udane: list[str] = []
    nieudane: list[str] = []
    metody: list[str] = []

    for nazwa, url in GMINY:
        try:
            wpisy, metoda = _wpisy_serwisu(url)
        except BladPobierania as e:
            nieudane.append(f"{nazwa}: {str(e)[:90]}")
            continue

        if not wpisy:
            nieudane.append(f"{nazwa}: nie rozpoznano listy aktualności")
            continue

        udane.append(nazwa)
        metody.append(f"{nazwa}: {metoda}")

        for wpis in wpisy[:30]:
            tresc = f"{wpis.get('tytul', '')} {wpis.get('tekst', '')}"
            if not dotyczy_terenu(tresc, SLOWA_KRYZYSOWE):
                continue

            data = wpis.get("data")
            if data:
                if data.tzinfo is None:
                    data = data.replace(tzinfo=granica.tzinfo)
                if data < granica:
                    continue

            pozycje.append(Pozycja(
                zrodlo="gminy",
                charakter="zdarzenie",
                typ=f"Komunikat — {nazwa}",
                tytul=wpis.get("tytul", "")[:200],
                opis=(wpis.get("tekst") or "")[:400],
                stopien=1,
                obowiazuje_od=data.isoformat() if data else None,
                link=pelny_adres(wpis.get("link"), url),
            ))

    if not udane:
        status.blad = " ;; ".join(nieudane)[:600]
        return Wynik(status=status)

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"{len(udane)} z {len(GMINY)} serwisów"
    if nieudane:
        status.uwaga += f" — bez: {', '.join(n.split(':')[0] for n in nieudane)}"

    print(f"  [uwaga gminy] metody: {' ;; '.join(metody)}")
    if nieudane:
        print(f"  [uwaga gminy] nieudane: {' ;; '.join(nieudane)[:400]}")

    # Deduplikacja: te same komunikaty bywają przepisywane między serwisami.
    unikalne: list[Pozycja] = []
    widziane = set()
    for pozycja in pozycje:
        klucz = pozycja.tytul.lower()[:80]
        if klucz in widziane:
            continue
        widziane.add(klucz)
        unikalne.append(pozycja)

    return Wynik(status=status, pozycje=unikalne[:25])
