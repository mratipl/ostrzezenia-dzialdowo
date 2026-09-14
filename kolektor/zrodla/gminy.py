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

from ..konfiguracja import (
    GMINY, GMINY_DNI_WSTECZ, SLOWA_INFORMACYJNE, SLOWA_KRYZYSOWE,
    SLOWA_OSTRZEZENIA, SLOWA_UTRUDNIENIA, SLOWA_WYKLUCZAJACE, SLOWA_ZAPOWIEDZI,
)
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..pomocnicze import bez_ogonkow
from ..siec import BladPobierania, pobierz_tekst
from .html_pomoc import (
    PRZEGLADARKA, adres_rss, data_po_frazie, data_z_tekstu, dotyczy_terenu,
    pelny_adres, wpisy_z_listy, wpisy_z_rss, zupa,
)


# Ścieżki kanałów sprawdzane, gdy strona nie ogłasza RSS-u znacznikiem link.
# Wiele serwisów gminnych działa na CMS-ach bez autodetekcji, ale kanał ma.
SCIEZKI_RSS = [
    "feed/", "rss", "rss.xml", "feed.xml", "?feed=rss2",
    "aktualnosci/rss", "rss/aktualnosci", "index.php?rss=1",
]


def _sprobuj_kanaly(url: str) -> tuple[list[dict], str]:
    """Kanał pod typową ścieżką. Wywoływane tylko, gdy autodetekcja zawiodła."""
    for sciezka in SCIEZKI_RSS:
        adres = url.rstrip("/") + "/" + sciezka if not sciezka.startswith("?") \
            else url.rstrip("/") + "/" + sciezka
        try:
            wpisy = wpisy_z_rss(pobierz_tekst(adres, PRZEGLADARKA, proby=1))
        except BladPobierania:
            continue
        if wpisy:
            return wpisy, f"RSS ({sciezka})"
    return [], ""


def _odrzucic(tresc: str) -> bool:
    """Czy wpis to uroczystość, zawody albo inna treść okolicznościowa."""
    plaski = bez_ogonkow(tresc)
    return any(bez_ogonkow(s) in plaski for s in SLOWA_WYKLUCZAJACE)


def _waga(tresc: str) -> int:
    """Stopień wpisu na podstawie jego treści.

    Kolejność sprawdzania ma znaczenie: najpierw ostrzeżenia, bo komunikat
    o awarii wodociągu POŁĄCZONY z informacją o wodzie niezdatnej do spożycia
    jest ostrzeżeniem, nie utrudnieniem.
    """
    maly = bez_ogonkow(tresc)

    # Zapowiedź rozstrzyga pierwsza, ale tylko gdy nie ma mowy o realnym
    # zagrożeniu: "planowane wyłączenie prądu" to utrudnienie, nie informacja.
    def pasuje(lista):
        return any(bez_ogonkow(s) in maly for s in lista)

    if pasuje(SLOWA_ZAPOWIEDZI) and pasuje(SLOWA_INFORMACYJNE) \
       and not pasuje(SLOWA_UTRUDNIENIA):
        return 0

    if pasuje(SLOWA_OSTRZEZENIA):
        return 2
    if pasuje(SLOWA_UTRUDNIENIA):
        return 1
    return 0


def _minela_data(tresc: str, moment) -> bool:
    """Czy wydarzenie opisane w treści już się odbyło.

    Szukamy daty w tytule i w opisie ("uruchomienie syren w dniu 01.09.2026",
    "w dniu 12 września nastąpi przerwa"). Po tym dniu wpis jest historią.
    Uwaga: wiele komunikatów pisze "dzisiaj" albo "jutro" — tego nie da się
    rozpoznać, dlatego oprócz tego działa okno czasowe zależne od wagi.
    """
    # Szukamy daty PO frazie wskazującej na termin zdarzenia. Zwykłe
    # data_z_tekstu brało pierwszą liczbę w treści, a przy wpisach parsowanych
    # z HTML-a jest to data PUBLIKACJI — przez co każdy komunikat wygasał
    # następnego dnia po ukazaniu się.
    data = data_po_frazie(
        tresc, "w dniu", "w dniach", "dnia", "w godzinach", "od dnia", "do dnia",
    )
    if not data:
        return False
    if data.tzinfo is None:
        data = data.replace(tzinfo=moment.tzinfo)
    return data.date() < moment.date()


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
    if wpisy:
        for wpis in wpisy:
            wpis.setdefault("data", data_z_tekstu(wpis.get("tekst", "")))
        return wpisy, f"HTML ({strategia})"

    # Parsowanie HTML-a nie dało wiarygodnej listy — sprawdzamy typowe
    # ścieżki kanałów, zanim uznamy serwis za nieobsługiwany.
    return _sprobuj_kanaly(url)


def komunikaty_gmin() -> Wynik:
    status = StatusZrodla(id="gminy", nazwa="Serwisy starostwa i gmin")

    moment = teraz()
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
            if _odrzucic(tresc):
                continue

            waga = _waga(tresc)

            data = wpis.get("data")
            if data:
                if data.tzinfo is None:
                    data = data.replace(tzinfo=moment.tzinfo)
                dni = GMINY_DNI_WSTECZ.get(waga, 3)
                if data < moment - timedelta(days=dni):
                    continue

            tytul = wpis.get("tytul", "")[:200]
            if _minela_data(tresc, moment):
                continue

            pozycje.append(Pozycja(
                zrodlo="gminy",
                charakter="zdarzenie",
                typ=f"Komunikat — {nazwa}",
                tytul=tytul,
                opis=(wpis.get("tekst") or "")[:400],
                stopien=waga,
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
