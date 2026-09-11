"""Pobieranie danych — jedno miejsce na timeouty, ponawianie i User-Agent."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .konfiguracja import PROBY, TIMEOUT, UA


class BladPobierania(Exception):
    pass


def pobierz_tekst(url: str, naglowki: dict[str, str] | None = None) -> str:
    naglowek = {"User-Agent": UA, "Accept": "*/*"}
    if naglowki:
        naglowek.update(naglowki)

    ostatni: Exception | None = None
    for proba in range(1, PROBY + 1):
        try:
            zadanie = urllib.request.Request(url, headers=naglowek)
            with urllib.request.urlopen(zadanie, timeout=TIMEOUT) as odp:
                surowe = odp.read()
            return surowe.decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            ostatni = e
            if proba < PROBY:
                time.sleep(2 * proba)

    raise BladPobierania(f"{url}: {ostatni}") from ostatni


def pobierz_json(url: str, naglowki: dict[str, str] | None = None):
    naglowek = {"Accept": "application/json"}
    if naglowki:
        naglowek.update(naglowki)
    tekst = pobierz_tekst(url, naglowek)
    try:
        return json.loads(tekst)
    except json.JSONDecodeError as e:
        urywek = tekst[:200].replace("\n", " ")
        raise BladPobierania(f"{url}: odpowiedź nie jest JSON-em ({urywek})") from e
