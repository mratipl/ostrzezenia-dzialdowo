"""Testy scraperów na sztucznym HTML-u. Bez sieci."""
from kolektor import siec
from kolektor.zrodla import html_pomoc, rcb, lasy

STRONA_KOMUNIKATY = """
<html><body><main>
<ul class="list">
 <li><a href="/web/rcb/silny-wiatr">Ostrzeżenie o silnym wietrze w województwie
     warmińsko-mazurskim</a><span>11 września 2026</span>
     <p>IMGW ostrzega przed porywami wiatru do 100 km/h.</p></li>
 <li><a href="/web/rcb/upal-slask">Upał na Śląsku i Opolszczyźnie</a>
     <span>10 września 2026</span><p>Temperatura do 34 stopni.</p></li>
 <li><a href="/web/rcb/alert-krajowy">Alert RCB w całej Polsce — burze</a>
     <span>12 września 2026</span><p>Możliwe gwałtowne burze z gradem.</p></li>
 <li><a href="/web/rcb/stare">Stary komunikat z Pomorza</a>
     <span>3 marca 2020</span><p>Nieaktualne.</p></li>
</ul></main></body></html>
"""

STRONA_STOPNIE = """
<html><body><p>Premier podpisał zarządzenia przedłużające obowiązywanie
stopni alarmowych. Od 1 września 2026 r. obowiązuje trzeci stopień alarmowy
CHARLIE na obszarze linii kolejowych zarządzanych przez PKP PLK oraz PKP LHS,
drugi stopień alarmowy BRAVO na pozostałym obszarze Rzeczypospolitej Polskiej,
a także drugi stopień alarmowy CRP BRAVO-CRP na całym obszarze kraju.
Stopnie obowiązują do 30 listopada 2026 r. do godz. 23:59.</p></body></html>
"""

STRONA_LASY = """
<html><body><table>
<tr><td>RDLP Białystok</td><td>1</td></tr>
<tr><td>RDLP Olsztyn</td><td>2</td></tr>
<tr><td>RDLP Gdańsk</td><td>0</td></tr>
</table></body></html>
"""

from bs4 import BeautifulSoup

def podstaw(mapowanie):
    def f(url, naglowki=None, proby=None, zapasowy_ua=True):
        for fragment, html in mapowanie.items():
            if fragment in url:
                return html
        raise siec.BladPobierania(f"nieobsłużony adres: {url}")
    html_pomoc.pobierz_tekst = f

print("== RCB: komunikaty, filtr terenu i wieku ==")
podstaw({"komunikaty": STRONA_KOMUNIKATY})
w = rcb.komunikaty()
print("   ok:", w.status.ok, "|", w.status.uwaga)
for p in w.pozycje:
    print("   -", p.tytul[:70])
tytuly = " ".join(p.tytul for p in w.pozycje)
assert w.status.ok
assert "warmińsko-mazurskim" in tytuly, "zgubiono komunikat dla regionu"
assert "całej Polsce" in tytuly, "zgubiono alert krajowy"
assert "Śląsku" not in tytuly, "przepuszczono komunikat spoza terenu"
assert "Pomorza" not in tytuly, "przepuszczono komunikat sprzed lat"

print("\n== RCB: stopnie alarmowe ==")
podstaw({"stopnie-alarmowe": STRONA_STOPNIE, "komunikaty": STRONA_STOPNIE})
w = rcb.stopnie_alarmowe()
print("   ok:", w.status.ok, "|", w.status.uwaga)
for p in w.pozycje:
    print(f"   [{p.stopien}] {p.tytul}  (do {(p.obowiazuje_do or '?')[:10]})")
etykiety = [p.tytul for p in w.pozycje]
assert any("CHARLIE" in e for e in etykiety), "nie rozpoznano CHARLIE"
assert any("BRAVO" in e for e in etykiety), "nie rozpoznano BRAVO"
assert any("CRP" in e for e in etykiety), "nie rozpoznano stopnia CRP"
assert all(p.charakter == "stan" for p in w.pozycje), "stopień musi być stanem, nie zdarzeniem"
assert w.pozycje[0].obowiazuje_do and "2026-11-30" in w.pozycje[0].obowiazuje_do

print("\n== Lasy: właściwa strefa, nie pierwsza z tabeli ==")
podstaw({"bazapozarow": STRONA_LASY})
import kolektor.zrodla.lasy as L
L._w_sezonie = lambda: True
w = L.zagrozenie_pozarowe()
print("   ", w.pozycje[0].tytul if w.pozycje else w.status.blad)
assert w.status.ok and w.pozycje[0].stopien == 2, "pobrano stopień nie z tej strefy"

print("\n== Lasy: poza sezonem to nie awaria ==")
L._w_sezonie = lambda: False
w = L.zagrozenie_pozarowe()
print("   ok:", w.status.ok, "|", w.status.uwaga)
assert w.status.ok and not w.pozycje

print("\n== Awaria parsera nie daje pustej listy ==")
podstaw({"komunikaty": "<html><body><p>przebudowa serwisu</p></body></html>"})
w = rcb.komunikaty()
print("   ok:", w.status.ok, "| blad:", w.status.blad)
assert not w.status.ok, "nierozpoznany układ musi być błędem, nie brakiem komunikatów"

print("\nWszystkie kontrole scraperów przeszły.")
