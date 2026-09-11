"""Kolektor. Uruchamiany z katalogu głównego repozytorium:

    python -m kolektor.main              # normalne zbieranie
    python -m kolektor.main --zrzut      # zapis surowych odpowiedzi do diagnostyki

Zasada nadrzędna: jeśli źródło nie odpowie, NIE udajemy, że nie ma zagrożeń.
Pokazujemy ostatnie znane dane oznaczone jako nieaktualne i wołamy o tym głośno.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .konfiguracja import (
    KATALOG_WYJSCIA, PROGI_SWIEZOSCI_MIN, PROG_DOMYSLNY_MIN,
)
from .model import StatusZrodla, Wynik, teraz
from .render import przygotuj, wzbogac, zapisz
from .zrodla import gddkia, gios, imgw, open_meteo

KORZEN = Path(__file__).resolve().parent.parent
WYJSCIE = KORZEN / KATALOG_WYJSCIA
SZABLONY = KORZEN / "szablony"

ZRODLA: list[Callable[[], Wynik]] = [
    imgw.ostrzezenia_meteo,
    imgw.ostrzezenia_hydro,
    gios.jakosc_powietrza,
    open_meteo.prognoza,
    gddkia.utrudnienia,
]


def wczytaj_poprzednie() -> dict[str, Any]:
    plik = WYJSCIE / "dane.json"
    if not plik.exists():
        return {}
    try:
        return json.loads(plik.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def poprzedni_stan(poprzednie: dict[str, Any]) -> dict[str, dict]:
    return {z["id"]: z for z in poprzednie.get("zrodla", []) if "id" in z}


def poprzednie_pozycje(poprzednie: dict[str, Any], zrodlo: str) -> list[dict]:
    wszystkie = poprzednie.get("zdarzenia", []) + poprzednie.get("stany", [])
    return [p for p in wszystkie if p.get("zrodlo") == zrodlo]


def czy_wygaslo(pozycja: dict, moment: datetime) -> bool:
    koniec = pozycja.get("obowiazuje_do")
    if not koniec:
        return False
    try:
        czas = datetime.fromisoformat(str(koniec).replace("Z", "+00:00"))
    except ValueError:
        return False
    if czas.tzinfo is None:
        czas = czas.replace(tzinfo=moment.tzinfo)
    return czas < moment


def minuty_od(iso: str | None, moment: datetime) -> int | None:
    if not iso:
        return None
    try:
        czas = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if czas.tzinfo is None:
        czas = czas.replace(tzinfo=moment.tzinfo)
    return max(0, int((moment - czas).total_seconds() // 60))


def zbierz() -> int:
    moment = teraz()
    poprzednie = wczytaj_poprzednie()
    stan_poprzedni = poprzedni_stan(poprzednie)

    statusy: list[StatusZrodla] = []
    pozycje: list[dict] = []
    bledy = 0

    for funkcja in ZRODLA:
        try:
            wynik = funkcja()
        except Exception as e:  # źródło nie może wywrócić całego kolektora
            wynik = Wynik(status=StatusZrodla(id=funkcja.__name__, nazwa=funkcja.__name__,
                                              blad=f"{type(e).__name__}: {e}"))

        status = wynik.status
        surowe = [p.do_slownika() for p in wynik.pozycje]

        if not status.ok:
            bledy += 1
            print(f"  [BŁĄD] {status.nazwa}: {status.blad}", file=sys.stderr)
            wczesniej = stan_poprzedni.get(status.id, {})
            status.pobrano = wczesniej.get("pobrano")
            surowe = [
                p for p in poprzednie_pozycje(poprzednie, status.id)
                if not czy_wygaslo(p, moment)
            ]
        else:
            print(f"  [OK]   {status.nazwa}: {len(surowe)} poz.")

        status.wiek_minut = minuty_od(status.pobrano, moment)
        prog = PROGI_SWIEZOSCI_MIN.get(status.id, PROG_DOMYSLNY_MIN)
        status.nieaktualne = status.wiek_minut is None or status.wiek_minut > prog

        statusy.append(status)
        pozycje.extend(wzbogac(p, status) for p in surowe)

    dane = przygotuj(pozycje, statusy, moment)
    zapisz(dane, WYJSCIE, SZABLONY)

    print(f"\nGotowe: {dane['naglowek']} · {len(pozycje)} pozycji · "
          f"{bledy} z {len(ZRODLA)} źródeł niedostępnych")
    return 0


def zrzut() -> int:
    """Zapisuje surowe odpowiedzi, żeby zobaczyć realną strukturę pól."""
    from .siec import BladPobierania, pobierz_tekst

    adresy = {
        "imgw-meteo": imgw.URL_METEO,
        "imgw-hydro": imgw.URL_HYDRO,
        "gios-stacje": gios.URL_STACJE,
        "open-meteo": open_meteo.URL,
        "gddkia": gddkia.ADRESY[0],
    }
    katalog = KORZEN / "diagnostyka"
    katalog.mkdir(exist_ok=True)

    for nazwa, url in adresy.items():
        try:
            tresc = pobierz_tekst(url)
        except BladPobierania as e:
            print(f"  [BŁĄD] {nazwa}: {e}", file=sys.stderr)
            continue
        plik = katalog / f"{nazwa}.txt"
        plik.write_text(tresc, encoding="utf-8")
        print(f"  [OK]   {nazwa}: {len(tresc)} znaków → {plik}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kolektor ostrzeżeń")
    parser.add_argument("--zrzut", action="store_true",
                        help="zapisz surowe odpowiedzi do katalogu diagnostyka/")
    argumenty = parser.parse_args()
    return zrzut() if argumenty.zrzut else zbierz()


if __name__ == "__main__":
    raise SystemExit(main())
