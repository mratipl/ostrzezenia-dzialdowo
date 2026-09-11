"""IMGW-PIB: ostrzeżenia meteorologiczne i hydrologiczne.

Endpointy z oficjalnej dokumentacji danepubliczne.imgw.pl/pl/apiinfo.
Struktura odpowiedzi nie jest tam opisana, więc pola czytamy tolerancyjnie,
a filtr terenu opiera się na wyszukaniu kodu TERYT w całej strukturze wpisu.
"""

from __future__ import annotations

from ..konfiguracja import TERYT_POWIATU
from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..pomocnicze import pole, zawiera_teryt
from ..siec import BladPobierania, pobierz_json

URL_METEO = "https://danepubliczne.imgw.pl/api/data/warningsmeteo"
URL_HYDRO = "https://danepubliczne.imgw.pl/api/data/warningshydro"

# Endpoint kontrolny: zawsze zwraca dane, niezależnie od sytuacji pogodowej.
URL_KONTROLNY = "https://danepubliczne.imgw.pl/api/data/synop"


def _api_zyje() -> bool:
    """Czy serwis IMGW w ogóle odpowiada.

    Endpointy ostrzeżeń potrafią zwrócić 404 zamiast pustej tablicy, gdy w kraju
    nie ma żadnego ostrzeżenia danego typu. Samo 404 jest więc dwuznaczne:
    może znaczyć "brak ostrzeżeń" albo "adres przestał istnieć". Rozstrzygamy to
    zapytaniem kontrolnym — bez tego uznanie 404 za brak zagrożeń byłoby
    dokładnie tą cichą dezinformacją, której unikamy.
    """
    try:
        pobierz_json(URL_KONTROLNY)
        return True
    except BladPobierania:
        return False


def _stopien(wpis: dict) -> int:
    surowy = pole(wpis, "stopien", "stopien_zagrozenia", "level", domyslnie=0)
    try:
        return max(0, min(3, int(str(surowy).strip()[:1])))
    except (TypeError, ValueError):
        return 0


def _na_pozycje(wpis: dict, zrodlo: str, etykieta: str) -> Pozycja:
    nazwa = pole(
        wpis,
        "nazwa_zdarzenia", "zjawisko", "nazwa", "event", "tresc",
        domyslnie=etykieta,
    )
    opis = pole(wpis, "tresc", "opis", "komentarz", "description", domyslnie="")
    prawdopodobienstwo = pole(wpis, "prawdopodobienstwo", "probability")

    dodatkowe = {}
    if prawdopodobienstwo:
        dodatkowe["prawdopodobienstwo"] = f"{prawdopodobienstwo}%"
    biuro = pole(wpis, "biuro", "office")
    if biuro:
        dodatkowe["biuro"] = str(biuro)

    return Pozycja(
        zrodlo=zrodlo,
        charakter="zdarzenie",
        typ=etykieta,
        tytul=str(nazwa),
        opis=str(opis),
        stopien=_stopien(wpis),
        obowiazuje_od=_czas(wpis, "obowiazuje_od", "waznosc_od", "od", "start"),
        obowiazuje_do=_czas(wpis, "obowiazuje_do", "waznosc_do", "do", "koniec", "stop"),
        dodatkowe=dodatkowe,
    )


def _czas(wpis: dict, *kandydaci: str) -> str | None:
    wartosc = pole(wpis, *kandydaci)
    return str(wartosc) if wartosc else None


def _zbierz(url: str, zrodlo: str, nazwa: str, etykieta: str) -> Wynik:
    status = StatusZrodla(id=zrodlo, nazwa=nazwa)
    try:
        dane = pobierz_json(url)
    except BladPobierania as e:
        if e.kod == 404 and _api_zyje():
            status.ok = True
            status.pobrano = teraz().isoformat(timespec="seconds")
            status.uwaga = "API odpowiada, endpoint zwrócił 404 — brak ostrzeżeń tego typu"
            return Wynik(status=status)
        status.blad = str(e)
        return Wynik(status=status)

    wpisy = dane if isinstance(dane, list) else [dane]
    pozycje = [
        _na_pozycje(w, zrodlo, etykieta)
        for w in wpisy
        if isinstance(w, dict) and zawiera_teryt(w, TERYT_POWIATU)
    ]

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    return Wynik(status=status, pozycje=pozycje)


def ostrzezenia_meteo() -> Wynik:
    return _zbierz(
        URL_METEO, "imgw-meteo", "IMGW – ostrzeżenia meteorologiczne", "Ostrzeżenie meteorologiczne"
    )


def ostrzezenia_hydro() -> Wynik:
    return _zbierz(
        URL_HYDRO, "imgw-hydro", "IMGW – ostrzeżenia hydrologiczne", "Ostrzeżenie hydrologiczne"
    )
