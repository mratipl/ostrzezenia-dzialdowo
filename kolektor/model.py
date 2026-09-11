"""Model danych.

Kluczowy podział, ustalony na etapie projektowania:

  zdarzenie — ma czas ważności, wygasa samo (ostrzeżenie IMGW, wypadek)
  stan      — obowiązuje do odwołania, nie miga (stopień alarmowy, indeks powietrza)

Oraz zasada nadrzędna: brak danych to NIE jest brak zagrożeń. Dlatego każde
źródło ma własny status i serwis musi go pokazać, zamiast milcząco wyświetlić
pustą listę.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def teraz() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Pozycja:
    """Pojedyncza informacja na tablicy."""

    zrodlo: str                       # identyfikator źródła, np. "imgw-meteo"
    charakter: str                    # "zdarzenie" albo "stan"
    typ: str                          # np. "Silny wiatr", "Jakość powietrza"
    tytul: str
    opis: str = ""
    stopien: int = 0                  # 0 = informacja, 1..3 = skala ostrzeżeń IMGW
    obowiazuje_od: str | None = None  # ISO 8601
    obowiazuje_do: str | None = None
    link: str | None = None
    dodatkowe: dict[str, Any] = field(default_factory=dict)

    @property
    def klucz(self) -> str:
        """Stabilny identyfikator do wykrywania zmian między uruchomieniami."""
        surowe = "|".join(
            [
                self.zrodlo,
                self.typ,
                self.tytul,
                self.obowiazuje_od or "",
                self.obowiazuje_do or "",
                str(self.stopien),
            ]
        )
        return hashlib.sha256(surowe.encode("utf-8")).hexdigest()[:16]

    def do_slownika(self) -> dict[str, Any]:
        d = asdict(self)
        d["klucz"] = self.klucz
        return d


@dataclass
class StatusZrodla:
    """Czy danemu źródłu można dziś wierzyć."""

    id: str
    nazwa: str
    ok: bool = False
    blad: str | None = None
    pobrano: str | None = None        # ISO 8601 ostatniego UDANEGO pobrania
    wiek_minut: int | None = None
    nieaktualne: bool = False

    def do_slownika(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Wynik:
    """To, co jedno źródło zwraca kolektorowi."""

    status: StatusZrodla
    pozycje: list[Pozycja] = field(default_factory=list)
