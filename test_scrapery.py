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

# Realistycznie długa tabela: nowa walidacja odrzuca krótkie strony opisowe,
# więc dane testowe muszą wyglądać jak prawdziwa tabela zbiorcza.
STRONA_LASY = "<html><body><h1>Stopień zagrożenia pożarowego lasu</h1><table>" + "".join(
    f"<tr><td>RDLP {n}</td><td>Nadleśnictwo {n}</td>"
    f"<td>strefa prognostyczna {i}</td><td>{s}</td>"
    f"<td>wilgotność ściółki {20 + i}%</td></tr>"
    for i, (n, s) in enumerate([
        ("Białystok", 1), ("Olsztyn", 2), ("Gdańsk", 0), ("Toruń", 1),
        ("Poznań", 1), ("Katowice", 3), ("Kraków", 2), ("Lublin", 1),
        ("Łódź", 0), ("Szczecin", 1), ("Wrocław", 2), ("Zielona Góra", 1),
    ])
) + "</table></body></html>"

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
podstaw({"bazapozarow": STRONA_LASY, "traxelektronik": STRONA_LASY})
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

print("\n== Stopnie: dojście przez artykuł z listy komunikatów ==")
LISTA_Z_WPISEM = """
<html><body><ul>
 <li><a href="/web/rcb/stopnie-alarmowe-przedluzone">Przedłużenie obowiązywania
     stopni alarmowych na terytorium RP</a><span>29 sierpnia 2026</span>
     <p>Premier podpisał zarządzenia przedłużające obowiązywanie stopni.</p></li>
 <li><a href="/web/rcb/cos-innego">Bezpieczne wakacje nad wodą — poradnik</a>
     <span>1 sierpnia 2026</span><p>Porady dla wypoczywających nad jeziorami.</p></li>
 <li><a href="/web/rcb/trzecie">Komunikat o burzach z gradem</a>
     <span>2 sierpnia 2026</span><p>Treść komunikatu o zjawiskach burzowych.</p></li>
</ul></body></html>
"""

def podstaw_dwustopniowo():
    def f(url, naglowki=None, proby=None, zapasowy_ua=True):
        if "stopnie-alarmowe-przedluzone" in url:
            return STRONA_STOPNIE                 # treść artykułu
        if "stopnie-alarmowe" in url or "premier" in url:
            return "<html><body><p>Strona informacyjna bez nazw.</p></body></html>"
        if "komunikaty" in url:
            return LISTA_Z_WPISEM
        raise siec.BladPobierania(f"nieobsłużony adres: {url}")
    html_pomoc.pobierz_tekst = f

podstaw_dwustopniowo()
w = rcb.stopnie_alarmowe()
print("   ok:", w.status.ok, "|", w.status.uwaga)
for p in w.pozycje:
    print(f"   [{p.stopien}] {p.tytul}")
assert w.status.ok, f"nie doszło do artykułu: {w.status.blad}"
assert any("CHARLIE" in p.tytul for p in w.pozycje)

print("\n== Stopnie: brak wpisu na liście → błąd z przykładami tytułów ==")
def bez_wpisu(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "komunikaty" in url:
        return """<html><body><main><ul>
          <li><a href="/a">Bezpieczne wakacje nad wodą — poradnik</a>
              <span>1 sierpnia 2026</span><p>Porady dla osób wypoczywających.</p></li>
          <li><a href="/b">Czad i ogień. Obudź czujność</a>
              <span>2 sierpnia 2026</span><p>Kampania informacyjna o zatruciach.</p></li>
          <li><a href="/c">Jak przygotować plecak ewakuacyjny</a>
              <span>3 sierpnia 2026</span><p>Lista rzeczy niezbędnych w drodze.</p></li>
        </ul></main></body></html>"""
    return "<html><body><p>nic</p></body></html>"
html_pomoc.pobierz_tekst = bez_wpisu
w = rcb.stopnie_alarmowe()
print("   blad:", (w.status.blad or "")[:180])
assert not w.status.ok and "Przykłady" in w.status.blad, "brak próbki tytułów w diagnostyce"

print("\nDodatkowe kontrole przeszły.")

print("\n== Stopnie: element menu nie może udawać artykułu ==")
LISTA_Z_MENU = """
<html><body>
<nav><ul>
  <li><a href="/web/rcb/co-robimy">Co robimy</a>
      <p>Zajmujemy się stopniami alarmowymi, alertami RCB i ostrzeżeniami.</p></li>
  <li><a href="/web/rcb/o-nas">O nas</a><p>Rządowe Centrum Bezpieczeństwa.</p></li>
</ul></nav>
<ul>
  <li><a href="/web/rcb/przedluzenie">Przedłużenie obowiązywania stopni alarmowych
      na terytorium Rzeczypospolitej</a><span>29 sierpnia 2026</span>
      <p>Premier podpisał zarządzenia przedłużające obowiązywanie stopni.</p></li>
  <li><a href="/web/rcb/inne">Bezpieczne wakacje nad wodą — poradnik</a>
      <span>28 sierpnia 2026</span><p>Porady dla wypoczywających nad wodą.</p></li>
  <li><a href="/web/rcb/czad">Czad i ogień — obudź czujność</a>
      <span>27 sierpnia 2026</span><p>Kampania informacyjna o zatruciach.</p></li>
</ul></body></html>
"""
def dwustopniowo_z_menu(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "przedluzenie" in url:
        return STRONA_STOPNIE
    if "co-robimy" in url:
        return "<html><body><p>Opis zadań centrum, bez nazw stopni.</p></body></html>"
    if "komunikaty" in url:
        return LISTA_Z_MENU
    return "<html><body><p>nic</p></body></html>"
html_pomoc.pobierz_tekst = dwustopniowo_z_menu
w = rcb.stopnie_alarmowe()
print("   ok:", w.status.ok, "|", w.status.uwaga or w.status.blad)
assert w.status.ok, f"wybrano zły wpis: {w.status.blad}"
assert any("CHARLIE" in p.tytul for p in w.pozycje)

print("\n== Lasy: strona opisowa odrzucona, tabela z danymi przyjęta ==")
OPISOWA = "<html><body><p>" + ("Mapa zagrożenia pożarowego lasu ustalanego zgodnie "
          "z metodą IBL obowiązującą w Polsce. " * 4) + "</p></body></html>"
TABELA = "<html><body><table>" + "".join(
    f"<tr><td>RDLP {n}</td><td>Nadleśnictwo X</td><td>{s}</td></tr>"
    for n, s in [("Białystok", 1), ("Olsztyn", 2), ("Gdańsk", 0)]
) + "</table><p>" + ("Strefa prognostyczna, wilgotność ściółki, stopień zagrożenia. " * 40) + "</p></body></html>"

def lasy_dwa(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "traxelektronik" in url:
        return OPISOWA                       # za krótka, bez danych
    if "mapa" in url:
        return TABELA
    return OPISOWA
html_pomoc.pobierz_tekst = lasy_dwa
L._w_sezonie = lambda: True
w = L.zagrozenie_pozarowe()
print("   ok:", w.status.ok, "|", (w.pozycje[0].tytul if w.pozycje else w.status.blad)[:70])
print("   uwaga:", w.status.uwaga)
assert w.status.ok and w.pozycje[0].stopien == 2, "nie pominięto strony opisowej"

print("\n== Lasy: same strony opisowe → błąd, nie stopień 0 ==")
html_pomoc.pobierz_tekst = lambda url, naglowki=None, proby=None, zapasowy_ua=True: OPISOWA
w = L.zagrozenie_pozarowe()
print("   blad:", (w.status.blad or "")[:110])
assert not w.status.ok and ("opisowa" in w.status.blad or "za mało" in w.status.blad)

print("\nKontrole poprawek przeszły.")
