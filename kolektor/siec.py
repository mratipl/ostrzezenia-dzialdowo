"""Pobieranie danych — jedno miejsce na timeouty, ponawianie i User-Agent."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .konfiguracja import PROBY, TIMEOUT, UA


class BladPobierania(Exception):
    def __init__(self, komunikat: str, kod: int | None = None):
        super().__init__(komunikat)
        self.kod = kod


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
                    return odp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                ostatni, ostatni_kod = e, e.code
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
