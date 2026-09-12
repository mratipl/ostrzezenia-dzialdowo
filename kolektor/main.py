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
    KATALOG_WYJSCIA, MIN_ODSTEP_MIN, PROGI_SWIEZOSCI_MIN,
    PROG_DOMYSLNY_MIN, ZRODLA_WYLACZONE,
)
from .model import StatusZrodla, Wynik, teraz
from .render import przygotuj, wzbogac, zapisz
from .zrodla import (
    airly, gddkia, gios, gminy, imgw, lasy, open_meteo, pse, rcb, wlasne,
)

KORZEN = Path(__file__).resolve().parent.parent
WYJSCIE = KORZEN / KATALOG_WYJSCIA
SZABLONY = KORZEN / "szablony"

# (identyfikator, funkcja) — identyfikator z góry, żeby dało się pominąć
# wyłączone źródło BEZ wykonywania zapytania.
ZRODLA: list[tuple[str, Callable[[], Wynik]]] = [
    ("imgw-meteo", imgw.ostrzezenia_meteo),
    ("imgw-hydro", imgw.ostrzezenia_hydro),
    ("gios", gios.jakosc_powietrza),
    ("airly", airly.pomiar),
    ("open-meteo", open_meteo.prognoza),
    ("gddkia", gddkia.utrudnienia),
    ("rcb", rcb.komunikaty),
    ("stopnie-alarmowe", rcb.stopnie_alarmowe),
    ("lasy", lasy.zagrozenie_pozarowe),
    ("pse", pse.bilans_mocy),
    ("gminy", gminy.komunikaty_gmin),
    ("wlasne", wlasne.komunikaty_wlasne),
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

    aktywne = [(i, f) for i, f in ZRODLA if i not in ZRODLA_WYLACZONE]

    for identyfikator, funkcja in aktywne:
        wczesniej = stan_poprzedni.get(identyfikator, {})

        # Kadencja: źródło z limitem dobowym pomijamy, jeśli pytaliśmy niedawno.
        odstep = MIN_ODSTEP_MIN.get(identyfikator)
        if odstep and wczesniej.get("pobrano"):
            wiek = minuty_od(wczesniej["pobrano"], moment)
            if wiek is not None and wiek < odstep:
                status = StatusZrodla(
                    id=identyfikator,
                    nazwa=wczesniej.get("nazwa", identyfikator),
                    ok=True,
                    pobrano=wczesniej["pobrano"],
                    wiek_minut=wiek,
                    uwaga=f"z pamięci — odpytywane co {odstep} min (limit dobowy)",
                )
                print(f"  [POMIN] {status.nazwa}: pobrane {wiek} min temu")
                statusy.append(status)
                pozycje.extend(
                    wzbogac(p, status) for p in poprzednie_pozycje(poprzednie, identyfikator)
                )
                continue

        try:
            wynik = funkcja()
        except Exception as e:  # źródło nie może wywrócić całego kolektora
            wynik = Wynik(status=StatusZrodla(id=identyfikator, nazwa=identyfikator,
                                              blad=f"{type(e).__name__}: {e}"))

        status = wynik.status
        surowe = [p.do_slownika() for p in wynik.pozycje]

        if not status.ok and status.uwaga and status.uwaga.startswith("nieaktywne"):
            continue          # źródło bez konfiguracji — pomijamy w ciszy

        if not status.ok:
            bledy += 1
            print(f"  [BŁĄD] {status.nazwa}: {status.blad}", file=sys.stderr)
            status.pobrano = wczesniej.get("pobrano")
            surowe = [
                p for p in poprzednie_pozycje(poprzednie, status.id)
                if not czy_wygaslo(p, moment)
            ]
        else:
            dopisek = f" ({status.uwaga})" if status.uwaga else ""
            print(f"  [OK]   {status.nazwa}: {len(surowe)} poz.{dopisek}")

        status.wiek_minut = minuty_od(status.pobrano, moment)
        prog = PROGI_SWIEZOSCI_MIN.get(status.id, PROG_DOMYSLNY_MIN)
        status.nieaktualne = status.wiek_minut is None or status.wiek_minut > prog

        statusy.append(status)
        pozycje.extend(wzbogac(p, status) for p in surowe)

    dane = przygotuj(pozycje, statusy, moment)
    zapisz(dane, WYJSCIE, SZABLONY)

    print(f"\nGotowe: {dane['naglowek']} · {len(pozycje)} pozycji · "
          f"{bledy} z {len(statusy)} źródeł niedostępnych")
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


def lista_airly() -> int:
    """Jednorazowe ustalenie identyfikatora instalacji. Kosztuje 1 zapytanie."""
    from .siec import BladPobierania

    print("Sonda trybu zbiorczego:", airly.sprawdz_tryb_zbiorczy(), "\n")

    try:
        instalacje = airly.instalacje_w_okolicy()
    except BladPobierania as e:
        print(f"Nie udało się pobrać listy instalacji: {e}", file=sys.stderr)
        return 1

    if not instalacje:
        print("W promieniu wyszukiwania nie ma żadnej instalacji Airly.")
        print("Źródło airly nie ma czego pokazywać — dopisz je do ZRODLA_WYLACZONE.")
        return 0

    print(f"Znaleziono {len(instalacje)} instalacji:\n")
    for i in instalacje:
        odleglosc = f"{i['km']} km" if i["km"] is not None else "? km"
        print(f"  id={i['id']:<8} {odleglosc:>9}   {i['miejscowosc']:<16} "
              f"{i['ulica']:<24} {i['sponsor']}".rstrip())
    print("\nWybrane identyfikatory wpisz do AIRLY_INSTALACJE "
          "w kolektor/konfiguracja.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Kolektor ostrzeżeń")
    parser.add_argument("--zrzut", action="store_true",
                        help="zapisz surowe odpowiedzi do katalogu diagnostyka/")
    parser.add_argument("--airly", action="store_true",
                        help="wypisz instalacje Airly w okolicy wraz z odległościami")
    argumenty = parser.parse_args()
    if argumenty.zrzut:
        return zrzut()
    if argumenty.airly:
        return lista_airly()
    return zbierz()


if __name__ == "__main__":
    raise SystemExit(main())
