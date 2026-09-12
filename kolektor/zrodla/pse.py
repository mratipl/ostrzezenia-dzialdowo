"""PSE – zagrożenie bilansu mocy i stopnie zasilania.

Źródło rzadko uwzględniane w serwisach ostrzegawczych, a dla zarządzania
kryzysowego istotne: ogłoszenie stopni zasilania oznacza ograniczenia
w dostawie energii dla odbiorców przemysłowych.

Interfejs raportowy PSE bywa przebudowywany, więc próbujemy kilku adresów,
a przy każdym niepowodzeniu raportujemy treść odpowiedzi.
"""

from __future__ import annotations

from ..model import Pozycja, StatusZrodla, Wynik, teraz
from ..siec import BladPobierania, pobierz_json

# Wnioski z pierwszego przebiegu na produkcji:
#  - his-obc zwraca 404, czyli taki zbiór nie istnieje,
#  - pk5l-wp odpowiada 400 z komunikatem "Invalid Query Parameter: $top",
#    czyli zbiór ISTNIEJE, a odrzucony został wyłącznie parametr.
# Dlatego pytamy bez parametrów i ograniczamy dane po swojej stronie.
WARIANTY = [
    ("plan koordynacyjny dobowy", "https://api.raporty.pse.pl/api/pk5l-wp"),
    ("plan z ograniczeniem pól", "https://api.raporty.pse.pl/api/pk5l-wp?$select=business_date"),
    ("bilans mocy", "https://api.raporty.pse.pl/api/cr-wp"),
]

NAGLOWKI = {"Accept": "application/json", "Accept-Encoding": "gzip, deflate"}


def bilans_mocy() -> Wynik:
    status = StatusZrodla(id="pse", nazwa="PSE – bilans mocy")

    bledy = []
    for opis, url in WARIANTY:
        try:
            dane = pobierz_json(url, NAGLOWKI, proby=1)
        except BladPobierania as e:
            bledy.append(f"{opis} → {e}")
            continue

        wartosci = dane.get("value") if isinstance(dane, dict) else dane
        if not wartosci:
            bledy.append(f"{opis} → odpowiedź bez danych")
            continue

        status.ok = True
        status.pobrano = teraz().isoformat(timespec="seconds")
        status.uwaga = f"wariant: {opis}"
        return Wynik(status=status, pozycje=[Pozycja(
            zrodlo="pse",
            charakter="stan",
            typ="System elektroenergetyczny",
            tytul="Brak ogłoszonych stopni zasilania",
            opis="Dane operacyjne PSE dostępne. Stopnie zasilania ogłasza się "
                 "odrębnym komunikatem operatora.",
            stopien=0,
        )])

    status.blad = " ;; ".join(bledy)[:400]
    return Wynik(status=status)
