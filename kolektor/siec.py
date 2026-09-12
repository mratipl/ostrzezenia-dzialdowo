"""Pobieranie danych — jedno miejsce na timeouty, ponawianie i User-Agent."""

from __future__ import annotations

import gzip
import json
import re
import time
import zlib
import urllib.error
import urllib.request

from .konfiguracja import PROBY, TIMEOUT, UA


class BladPobierania(Exception):
    def __init__(self, komunikat: str, kod: int | None = None):
        super().__init__(komunikat)
        self.kod = kod


def _rozpakuj(surowe: bytes, kodowanie: str | None) -> bytes:
    """urllib nie rozpakowuje sam, a bez Accept-Encoding część serwerów odrzuca ruch."""
    if kodowanie:
        nazwa = kodowanie.lower()
        try:
            if "gzip" in nazwa:
                return gzip.decompress(surowe)
            if "deflate" in nazwa:
                return zlib.decompress(surowe, -zlib.MAX_WBITS)
        except (OSError, zlib.error):
            pass
    return surowe


def _znajdz_kodowanie(surowe: bytes, typ_tresci: str | None) -> str | None:
    """Kodowanie z nagłówka Content-Type albo ze znacznika meta w HTML-u."""
    if typ_tresci:
        m = re.search(r"charset=\s*([\w-]+)", typ_tresci, re.IGNORECASE)
        if m:
            return m.group(1)

    # Znacznik meta szukamy w surowych bajtach — jeszcze nie wiemy, jak dekodować.
    poczatek = surowe[:2048].decode("ascii", errors="ignore")
    m = re.search(r"charset=[\"\']?\s*([\w-]+)", poczatek, re.IGNORECASE)
    return m.group(1) if m else None


def _odkoduj(surowe: bytes, kodowanie: str | None, typ_tresci: str | None = None) -> str:
    """Rozpakowanie i zdekodowanie odpowiedzi.

    Kodowanie NIE jest na sztywno UTF-8. Starsze polskie serwisy publiczne
    nadal używają ISO-8859-2 i windows-1250; zdekodowane jako UTF-8 dają
    krzaki w miejscu polskich znaków, co skutecznie psuje dopasowywanie nazw.
    """
    surowe = _rozpakuj(surowe, kodowanie)

    proby = []
    wskazane = _znajdz_kodowanie(surowe, typ_tresci)
    if wskazane:
        proby.append(wskazane)
    proby += ["utf-8", "cp1250", "iso-8859-2"]

    for nazwa in proby:
        try:
            return surowe.decode(nazwa)
        except (UnicodeDecodeError, LookupError):
            continue
    return surowe.decode("utf-8", errors="replace")


def _tresc_bledu(e: urllib.error.HTTPError) -> str:
    try:
        surowe = e.read()[:400]
    except Exception:
        return ""
    naglowki = e.headers if e.headers else None
    tekst = _odkoduj(
        surowe,
        naglowki.get("Content-Encoding") if naglowki else None,
        naglowki.get("Content-Type") if naglowki else None,
    )
    return " ".join(tekst.split())[:250]


# Część serwerów publicznych odrzuca nietypowe User-Agenty, zwracając 403 lub 406.
# Wolimy przedstawiać się uczciwie, ale gdy to nie działa — próbujemy neutralnie.
UA_ZAPASOWY = "Mozilla/5.0 (compatible; OstrzezeniaBot/1.0)"


def pobierz_tekst(
    url: str,
    naglowki: dict[str, str] | None = None,
    proby: int | None = None,
    zapasowy_ua: bool = True,
) -> str:
    """proby i zapasowy_ua pozwalają ograniczyć liczbę żądań.

    Ma to znaczenie przy API z dziennym limitem: domyślne ponawianie razem ze
    zmianą User-Agenta może wygenerować do sześciu żądań na jedno wywołanie.
    """
    limit = proby if proby is not None else PROBY
    agenci = (UA, UA_ZAPASOWY) if zapasowy_ua else (UA,)
    ostatni: Exception | None = None
    ostatni_kod: int | None = None

    for agent in agenci:
        naglowek = {"User-Agent": agent, "Accept": "*/*"}
        if naglowki:
            naglowek.update(naglowki)

        for proba in range(1, limit + 1):
            try:
                zadanie = urllib.request.Request(url, headers=naglowek)
                with urllib.request.urlopen(zadanie, timeout=TIMEOUT) as odp:
                    return _odkoduj(
                        odp.read(),
                        odp.headers.get("Content-Encoding"),
                        odp.headers.get("Content-Type"),
                    )
            except urllib.error.HTTPError as e:
                # Treść odpowiedzi błędu bywa najcenniejszą informacją: przy 406
                # serwery zwykle wypisują, jakie formaty są akceptowalne.
                tresc = _tresc_bledu(e)
                ostatni = BladPobierania(
                    f"{url}: HTTP Error {e.code}{f' — {tresc}' if tresc else ''}", e.code
                )
                ostatni_kod = e.code
                if e.code in (403, 406):
                    break          # zmiana agenta ma sens, ponawianie nie
                if e.code == 404:
                    raise BladPobierania(f"{url}: HTTP Error 404: Not Found", 404) from e
                if proba < limit:
                    time.sleep(2 * proba)
            except (urllib.error.URLError, OSError) as e:
                ostatni = e
                if proba < limit:
                    time.sleep(2 * proba)

    if isinstance(ostatni, BladPobierania):
        raise ostatni
    raise BladPobierania(f"{url}: {ostatni}", ostatni_kod) from ostatni


def pobierz_json(
    url: str,
    naglowki: dict[str, str] | None = None,
    proby: int | None = None,
    zapasowy_ua: bool = True,
):
    naglowek = {"Accept": "application/json"}
    if naglowki:
        naglowek.update(naglowki)
    tekst = pobierz_tekst(url, naglowek, proby=proby, zapasowy_ua=zapasowy_ua)
    try:
        return json.loads(tekst)
    except json.JSONDecodeError as e:
        urywek = tekst[:200].replace("\n", " ")
        raise BladPobierania(f"{url}: odpowiedź nie jest JSON-em ({urywek})") from e
