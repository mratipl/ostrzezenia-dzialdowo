"""Komunikaty własne — plik JSON w repozytorium.

Furtka na informacje, które istnieją tylko na Facebooku jednostek albo
pojawiają się szybciej niż na stronach urzędowych. Dopisujesz wpis przez
edytor GitHuba, kolektor pokazuje go obok danych automatycznych.

Świadome ograniczenie: tu wchodzi WYŁĄCZNIE treść już upubliczniona.
Informacje uzyskane służbowo nie należą do prywatnego serwisu.

Format pliku dane/komunikaty.json:

[
  {
    "tytul": "Zaginięcie osoby — poszukiwania w gminie Rybno",
    "opis": "Policja prosi o kontakt osoby, które widziały...",
    "stopien": 2,
    "charakter": "zdarzenie",
    "od": "2026-09-12",
    "do": "2026-09-20",
    "link": "https://..."
  }
]

Wpisy z przeszłą datą "do" są pomijane, więc nie trzeba ich usuwać ręcznie.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..model import Pozycja, StatusZrodla, Wynik, teraz

PLIK = Path(__file__).resolve().parent.parent.parent / "dane" / "komunikaty.json"


def _data(wartosc) -> datetime | None:
    if not wartosc:
        return None
    try:
        czas = datetime.fromisoformat(str(wartosc).replace("Z", "+00:00"))
    except ValueError:
        return None
    return czas.replace(tzinfo=teraz().tzinfo) if czas.tzinfo is None else czas


def komunikaty_wlasne() -> Wynik:
    status = StatusZrodla(id="wlasne", nazwa="Komunikaty własne")

    if not PLIK.exists():
        status.ok = True
        status.pobrano = teraz().isoformat(timespec="seconds")
        status.uwaga = "brak pliku dane/komunikaty.json (to nie błąd)"
        return Wynik(status=status)

    try:
        wpisy = json.loads(PLIK.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # Literówka w JSON-ie nie może przejść niezauważona: to jedyne źródło,
        # w którym treść wpisuje człowiek.
        status.blad = f"nieprawidłowy JSON w dane/komunikaty.json: {e}"
        return Wynik(status=status)

    if not isinstance(wpisy, list):
        status.blad = "plik musi zawierać listę wpisów w nawiasach kwadratowych"
        return Wynik(status=status)

    moment = teraz()
    pozycje: list[Pozycja] = []
    pominiete = 0

    for wpis in wpisy:
        if not isinstance(wpis, dict) or not wpis.get("tytul"):
            pominiete += 1
            continue

        do_kiedy = _data(wpis.get("do"))
        if do_kiedy and do_kiedy < moment:
            continue          # wygasł, zostaje w pliku jako archiwum

        od = _data(wpis.get("od"))
        try:
            stopien = max(0, min(3, int(wpis.get("stopien", 1))))
        except (TypeError, ValueError):
            stopien = 1

        charakter = wpis.get("charakter", "zdarzenie")
        if charakter not in ("zdarzenie", "stan"):
            charakter = "zdarzenie"

        pozycje.append(Pozycja(
            zrodlo="wlasne",
            charakter=charakter,
            typ="Komunikat redakcyjny",
            tytul=str(wpis["tytul"])[:200],
            opis=str(wpis.get("opis", ""))[:600],
            stopien=stopien,
            obowiazuje_od=od.isoformat() if od else None,
            obowiazuje_do=do_kiedy.isoformat() if do_kiedy else None,
            link=wpis.get("link"),
        ))

    status.ok = True
    status.pobrano = teraz().isoformat(timespec="seconds")
    status.uwaga = f"{len(pozycje)} aktywnych z {len(wpisy)} w pliku"
    if pominiete:
        status.uwaga += f", {pominiete} wpisów bez tytułu pominięto"
    return Wynik(status=status, pozycje=pozycje)
