"""Zamiana zebranych danych na dane.json i index.html."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .konfiguracja import ATRYBUCJA, NAZWA_POWIATU
from .model import Pozycja, StatusZrodla

STREFA = timezone(timedelta(hours=1))  # zapasowo, gdy brak zoneinfo
try:
    from zoneinfo import ZoneInfo

    STREFA = ZoneInfo("Europe/Warsaw")
except Exception:  # pragma: no cover
    pass

NAZWY_STOPNI = {
    0: "Brak ostrzeżeń",
    1: "Ostrzeżenie 1. stopnia",
    2: "Ostrzeżenie 2. stopnia",
    3: "Ostrzeżenie 3. stopnia",
}


def lokalnie(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        czas = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if czas.tzinfo is None:
        czas = czas.replace(tzinfo=timezone.utc)
    return czas.astimezone(STREFA).strftime("%d.%m.%Y, %H:%M")


def _okres(p: Pozycja) -> str:
    od, do = lokalnie(p.obowiazuje_od), lokalnie(p.obowiazuje_do)
    if od and do:
        return f"od {od} do {do}"
    if do:
        return f"do {do}"
    if od:
        return f"od {od}"
    return ""


def _wiek(minuty: int | None) -> str:
    if minuty is None:
        return "nieznany czas"
    if minuty < 90:
        return f"{minuty} min"
    godziny = minuty // 60
    if godziny < 36:
        return f"{godziny} godz."
    return f"{godziny // 24} dni"


def przygotuj(
    pozycje: list[dict[str, Any]],
    statusy: list[StatusZrodla],
    wygenerowano: datetime,
) -> dict[str, Any]:
    """Buduje słownik podawany zarówno do JSON-a, jak i do szablonu."""
    zdarzenia = [p for p in pozycje if p["charakter"] == "zdarzenie"]
    stany = [p for p in pozycje if p["charakter"] == "stan"]

    zdarzenia.sort(key=lambda p: (-p["stopien"], p["typ"]))
    stany.sort(key=lambda p: (-p["stopien"], p["typ"]))

    # Stopień liczymy ze WSZYSTKICH wyświetlanych zdarzeń, także tych z
    # nieodświeżonych źródeł. Inaczej awaria pobierania zamieniałaby aktywne
    # ostrzeżenie w komunikat "brak ostrzeżeń" — czyli w cichą dezinformację.
    najwyzszy = max((p["stopien"] for p in zdarzenia), default=0)
    niedostepne = [z.nazwa for z in statusy if not z.ok]
    nigdy_nie_pobrane = [z.nazwa for z in statusy if not z.pobrano]

    # Nagłówek napędzają tylko zdarzenia ze stopniem co najmniej 1. Zapowiedź
    # treningu syren jest informacją, nie ostrzeżeniem, i nie może zajmować
    # miejsca zarezerwowanego dla realnego zagrożenia.
    if najwyzszy >= 1:
        naglowek = NAZWY_STOPNI[najwyzszy] + " — " + zdarzenia[0]["tytul"].lower()
        klasa = f"s{najwyzszy}"
    elif zdarzenia:
        naglowek = "Brak ostrzeżeń"
        klasa = "s0"
    elif not any(z.ok for z in statusy):
        naglowek = "Brak danych"
        klasa = "sbrak"
    else:
        naglowek = "Brak ostrzeżeń"
        klasa = "s0"

    return {
        "powiat": NAZWA_POWIATU,
        "wygenerowano": lokalnie(wygenerowano.isoformat()),
        "wygenerowano_iso": wygenerowano.isoformat(timespec="seconds"),
        "naglowek": naglowek,
        "klasa_statusu": klasa,
        "najwyzszy_stopien": najwyzszy,
        "zdarzenia": zdarzenia,
        "stany": stany,
        "zrodla": [
            {**z.do_slownika(), "pobrano_ladnie": lokalnie(z.pobrano)} for z in statusy
        ],
        "zrodla_niedostepne": niedostepne,
        "zrodla_bez_danych": nigdy_nie_pobrane,
        "atrybucja": ATRYBUCJA,
    }


def wzbogac(pozycja: dict[str, Any], status: StatusZrodla) -> dict[str, Any]:
    """Dokłada pola potrzebne tylko do wyświetlenia."""
    przestarzale = not status.ok
    pozycja["przestarzale"] = przestarzale
    pozycja["wiek"] = _wiek(status.wiek_minut) if przestarzale else None
    tymczasowa = Pozycja(
        zrodlo=pozycja["zrodlo"],
        charakter=pozycja["charakter"],
        typ=pozycja["typ"],
        tytul=pozycja["tytul"],
        obowiazuje_od=pozycja.get("obowiazuje_od"),
        obowiazuje_do=pozycja.get("obowiazuje_do"),
    )
    pozycja["okres"] = _okres(tymczasowa)
    return pozycja


def zapisz(dane: dict[str, Any], katalog: Path, katalog_szablonow: Path) -> None:
    katalog.mkdir(parents=True, exist_ok=True)

    (katalog / "dane.json").write_text(
        json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    srodowisko = Environment(
        loader=FileSystemLoader(str(katalog_szablonow)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    szablon = srodowisko.get_template("index.html.j2")
    (katalog / "index.html").write_text(szablon.render(**dane), encoding="utf-8")
