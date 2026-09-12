"""Wspólna warstwa dla źródeł wymagających parsowania HTML.

Parsery HTML psują się przy każdym przemodelowaniu strony, w przeciwieństwie
do API. Dlatego zamiast jednego selektora próbujemy kilku strategii po kolei
i raportujemy, która zadziałała — ta sama zasada, która pozwoliła rozgryźć
GIOŚ. Gdy żadna nie zwróci wpisów, źródło melduje błąd, a nie pustą listę
udającą brak komunikatów.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..siec import pobierz_tekst

# Nagłówki przeglądarki — bez kompresji część serwerów odrzuca ruch jako bota.
PRZEGLADARKA = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Connection": "keep-alive",
}

MIESIACE = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
    "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
    "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}


def zupa(url: str, proby: int = 2) -> BeautifulSoup:
    html = pobierz_tekst(url, PRZEGLADARKA, proby=proby)
    return BeautifulSoup(html, "html.parser")


def czysty(tekst: str) -> str:
    return " ".join((tekst or "").split())


def wpisy_z_listy(dokument: BeautifulSoup, minimum_znakow: int = 25) -> tuple[list[dict], str]:
    """Wyciąga wpisy listy aktualności. Zwraca (wpisy, nazwa strategii).

    Każdy wpis to {'tytul', 'link', 'tekst'}. Kolejne strategie odpowiadają
    typowym układom serwisów rządowych i samorządowych.
    """
    strategie = [
        ("article", lambda d: d.find_all("article")),
        ("li z linkiem", lambda d: [
            e for e in d.find_all("li") if e.find("a") and len(czysty(e.get_text())) > minimum_znakow
        ]),
        ("nagłówek h2/h3 z linkiem", lambda d: [
            e for e in d.find_all(["h2", "h3"]) if e.find("a")
        ]),
        ("kafelki div", lambda d: [
            e for e in d.find_all("div", class_=re.compile(r"(item|card|tile|news|aktual)", re.I))
            if e.find("a")
        ]),
    ]

    for nazwa, pobierz in strategie:
        wpisy = []
        widziane = set()
        for element in pobierz(dokument):
            tekst = czysty(element.get_text(" "))
            if len(tekst) < minimum_znakow:
                continue
            odnosnik = element.find("a")
            tytul = czysty(odnosnik.get_text()) if odnosnik else tekst[:120]
            if not tytul or tytul in widziane:
                continue
            widziane.add(tytul)
            wpisy.append({
                "tytul": tytul[:200],
                "link": odnosnik.get("href") if odnosnik else None,
                "tekst": tekst[:600],
            })
        if len(wpisy) >= 2:
            return wpisy, nazwa

    return [], ""


def pelny_adres(link: str | None, baza: str) -> str | None:
    if not link:
        return None
    if link.startswith("http"):
        return link
    if link.startswith("/"):
        korzen = "/".join(baza.split("/")[:3])
        return korzen + link
    return baza.rstrip("/") + "/" + link


def data_z_tekstu(tekst: str) -> datetime | None:
    """Rozpoznaje '30 listopada 2026' oraz '2026-11-30' i '30.11.2026'."""
    t = (tekst or "").lower()

    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", t)
    if m and m.group(2) in MIESIACE:
        try:
            return datetime(int(m.group(3)), MIESIACE[m.group(2)], int(m.group(1)))
        except ValueError:
            pass

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def data_po_frazie(tekst: str, *frazy: str) -> datetime | None:
    """Data występująca PO podanej frazie, np. 'obowiązują do 30 listopada 2026'.

    Bez tego rozróżnienia data_z_tekstu zwraca pierwszą datę w tekście, czyli
    zwykle dzień wejścia w życie, a nie termin wygaśnięcia.
    """
    maly = (tekst or "").lower()
    najlepsza = None
    for fraza in frazy:
        for dopasowanie in re.finditer(re.escape(fraza.lower()), maly):
            ogon = maly[dopasowanie.end():dopasowanie.end() + 60]
            data = data_z_tekstu(ogon)
            if data and (najlepsza is None or data > najlepsza):
                najlepsza = data
    return najlepsza


def dotyczy_terenu(tekst: str, frazy: list[str]) -> bool:
    maly = (tekst or "").lower()
    return any(f.lower() in maly for f in frazy)
