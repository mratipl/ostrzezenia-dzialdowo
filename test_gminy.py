"""Testy źródła gmin i komunikatów własnych. Bez sieci."""
import json, pathlib
from kolektor import siec
from kolektor.zrodla import html_pomoc, gminy, wlasne

STRONA_Z_RSS = """
<html><head>
<link rel="alternate" type="application/rss+xml" href="/feed/" title="Kanał">
</head><body><p>Strona główna</p></body></html>
"""

KANAL = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
 <item><title>Przerwa w dostawie wody w Burkacie</title>
   <link>https://example.pl/woda</link>
   <pubDate>Fri, 11 Sep 2026 08:00:00 +0200</pubDate>
   <description><![CDATA[<p>W dniu 12 września nastąpi przerwa w dostawie wody.</p>]]></description></item>
 <item><title>Dożynki gminne 2026</title>
   <link>https://example.pl/dozynki</link>
   <pubDate>Fri, 11 Sep 2026 09:00:00 +0200</pubDate>
   <description>Zapraszamy na dożynki i konkurs wieńców.</description></item>
 <item><title>Trening systemu ostrzegania — syreny</title>
   <link>https://example.pl/syreny</link>
   <pubDate>Thu, 10 Sep 2026 07:00:00 +0200</pubDate>
   <description>W piątek uruchomione zostaną syreny alarmowe.</description></item>
 <item><title>Awaria sieci wodociągowej z 2019 roku</title>
   <link>https://example.pl/stare</link>
   <pubDate>Mon, 04 Mar 2019 07:00:00 +0100</pubDate>
   <description>Archiwalne.</description></item>
</channel></rss>
"""

# Realistyczna lista aktualności: data przy KAŻDYM wpisie. To właśnie datami
# odróżniamy aktualności od menu, więc dane testowe muszą je mieć.
STRONA_BEZ_RSS = """
<html><body><main><ul>
 <li><a href="/a">Ostrzeżenie o silnym wiatrze dla gminy</a>
     <time>11 września 2026</time>
     <p>Prosimy o zachowanie ostrożności i zabezpieczenie przedmiotów.</p></li>
 <li><a href="/b">Nowy plac zabaw otwarty przy szkole</a>
     <time>10 września 2026</time>
     <p>Uroczyste otwarcie placu zabaw dla najmłodszych mieszkańców.</p></li>
 <li><a href="/c">Zebranie wiejskie w sprawie funduszu sołeckiego</a>
     <time>9 września 2026</time>
     <p>Porządek obrad zebrania oraz projekt podziału środków.</p></li>
</ul></main></body></html>
"""

def fałszywy(url, naglowki=None, proby=None, zapasowy_ua=True):
    # Serwisy bez kanału: żadna ścieżka RSS nie odpowiada, zostaje HTML.
    if "plosnica" in url or "gminarybno" in url:
        if url.rstrip("/").endswith((".xml", "rss", "feed", "feed/", "rss=1")) \
           or "feed" in url.split("/")[-1] or "rss" in url.split("/")[-1]:
            raise siec.BladPobierania("HTTP Error 404: Not Found", 404)
        return STRONA_BEZ_RSS
    if "feed" in url:
        return KANAL
    if "powiatdzialdowski" in url:
        raise siec.BladPobierania("HTTP Error 503 — Service Unavailable", 503)
    return STRONA_Z_RSS
html_pomoc.pobierz_tekst = fałszywy
gminy.pobierz_tekst = fałszywy

print("== Gminy: RSS, HTML i awaria jednego serwisu ==")
w = gminy.komunikaty_gmin()
print("   ok:", w.status.ok, "| uwaga:", w.status.uwaga)
for p in w.pozycje:
    print("   -", p.typ, "|", p.tytul[:52])
tytuly = " ".join(p.tytul for p in w.pozycje)
assert w.status.ok, "awaria jednego serwisu nie może zgasić całego źródła"
assert "Przerwa w dostawie wody" in tytuly, "zgubiono komunikat o wodzie"
assert "syreny" in tytuly.lower(), "zgubiono trening syren"
assert "Ostrzeżenie o silnym wiatrze" in tytuly, "zgubiono wpis z HTML-a"
assert "Dożynki" not in tytuly, "przepuszczono treść niezwiązaną z ZK"
assert "plac zabaw" not in tytuly.lower(), "przepuszczono treść niezwiązaną z ZK"
assert "2019" not in tytuly, "przepuszczono wpis sprzed lat"
assert "Starostwo" in (w.status.uwaga or ""), "brak informacji o nieudanym serwisie"

print("\n== Gminy: deduplikacja przepisanych komunikatów ==")
def ten_sam(url, naglowki=None, proby=None, zapasowy_ua=True):
    return KANAL if "feed" in url else STRONA_Z_RSS
html_pomoc.pobierz_tekst = ten_sam
w = gminy.komunikaty_gmin()
woda = [p for p in w.pozycje if "Przerwa w dostawie" in p.tytul]
print(f"   ten sam komunikat na 7 serwisach → {len(woda)} pozycji")
assert len(woda) == 1, "brak deduplikacji"

print("\n== Komunikaty własne ==")
KATALOG = pathlib.Path(wlasne.PLIK).parent
KATALOG.mkdir(parents=True, exist_ok=True)
wlasne.PLIK.write_text(json.dumps([
    {"tytul": "Poszukiwania osoby zaginionej", "opis": "Policja prosi o kontakt.",
     "stopien": 2, "od": "2026-09-12", "do": "2026-12-31"},
    {"tytul": "Wygasły komunikat", "opis": "Nie powinien się pokazać",
     "do": "2020-01-01"},
    {"bez_tytulu": True},
], ensure_ascii=False), encoding="utf-8")
w = wlasne.komunikaty_wlasne()
print("   ok:", w.status.ok, "|", w.status.uwaga)
for p in w.pozycje:
    print(f"   [{p.stopien}] {p.tytul}")
assert len(w.pozycje) == 1 and w.pozycje[0].stopien == 2
assert "pominięto" in w.status.uwaga

print("\n== Komunikaty własne: zepsuty JSON to błąd, nie cisza ==")
wlasne.PLIK.write_text('[{"tytul": "brak nawiasu"', encoding="utf-8")
w = wlasne.komunikaty_wlasne()
print("   blad:", (w.status.blad or "")[:80])
assert not w.status.ok

print("\n== Komunikaty własne: brak pliku to nie awaria ==")
wlasne.PLIK.unlink()
w = wlasne.komunikaty_wlasne()
print("   ok:", w.status.ok, "|", w.status.uwaga)
assert w.status.ok and not w.pozycje
wlasne.PLIK.write_text("[]", encoding="utf-8")

print("\nWszystkie kontrole przeszły.")

print("\n== Nawigacja gov.pl nie może udawać listy komunikatów ==")
MENU_GOVPL = """
<html><body>
<nav class="main-nav"><ul>
  <li><a href="#stopka">Przejdź do sekcji Stopka gov.pl</a></li>
  <li><a href="/mobywatel">Logowanie do panelu mObywatel</a></li>
  <li><a href="/urzedy">Urzędy, instytucje i placówki RP</a></li>
  <li><a href="/ua">Сайт для громадян України – Serwis dla obywateli Ukrainy</a></li>
  <li><a href="/migowy">Otwórz okno z tłumaczem języka migowego</a></li>
</ul></nav>
<footer><ul>
  <li><a href="/dostepnosc">Deklaracja dostępności serwisu</a></li>
  <li><a href="/prywatnosc">Polityka prywatności i cookies</a></li>
</ul></footer>
<div class="content"><p>Treść bez listy aktualności.</p></div>
</body></html>
"""
wpisy, strategia = html_pomoc.wpisy_z_listy(
    html_pomoc.BeautifulSoup(MENU_GOVPL, "html.parser"))
print(f"   rozpoznanych wpisów: {len(wpisy)} (strategia: {strategia or 'brak'})")
assert not wpisy, f"nawigacja nadal przechodzi jako komunikaty: {[w['tytul'] for w in wpisy]}"

print("\n== Prawdziwa lista aktualności nadal przechodzi ==")
PRAWDZIWA = """
<html><body>
<nav><ul><li><a href="/x">Przejdź do treści</a></li></ul></nav>
<main><ul class="news">
 <li><a href="/a">Przerwa w dostawie wody w Burkacie i Księżym Dworze</a>
     <time>11 września 2026</time>
     <p>W dniu 12 września nastąpi przerwa w dostawie wody dla mieszkańców.</p></li>
 <li><a href="/b">Trening systemu wykrywania i alarmowania</a>
     <time>10 września 2026</time>
     <p>W piątek zostaną uruchomione syreny alarmowe na terenie gminy.</p></li>
 <li><a href="/c">Otwarcie nowego placu zabaw przy szkole</a>
     <time>9 września 2026</time>
     <p>Zapraszamy mieszkańców na uroczyste otwarcie placu zabaw.</p></li>
</ul></main></body></html>
"""
wpisy, strategia = html_pomoc.wpisy_z_listy(
    html_pomoc.BeautifulSoup(PRAWDZIWA, "html.parser"))
print(f"   rozpoznanych wpisów: {len(wpisy)} (strategia: {strategia})")
for w in wpisy:
    print("   -", w["tytul"][:60])
assert len(wpisy) == 3, f"zgubiono prawdziwe aktualności: {len(wpisy)}"
assert not any("Przejdź" in w["tytul"] for w in wpisy)

print("\nKontrole filtra nawigacji przeszły.")

print("\n== Waga wpisów: trening syren to nie ostrzeżenie ==")
PRZYPADKI = [
    ("Komunikat dla mieszkańców - uruchomienie syren w dniu 20.12.2026",
     "Informujemy o treningu systemu wykrywania i alarmowania.", 0),
    ("Przerwa w dostawie wody w Burkacie",
     "W dniu 20 grudnia nastąpi przerwa w dostawie wody.", 1),
    ("Awaria sieci wodociągowej — woda niezdatna do spożycia",
     "Zakaz spożywania wody do odwołania.", 2),
    ("Ostrzeżenie meteorologiczne — silny wiatr",
     "IMGW ostrzega przed porywami.", 2),
    ("Planowane wyłączenie prądu w Uzdowie",
     "Energa informuje o wyłączeniu prądu.", 1),
]
for tytul, opis, oczekiwany in PRZYPADKI:
    waga = gminy._waga(f"{tytul} {opis}")
    znak = "✓" if waga == oczekiwany else "✗"
    print(f"   {znak} [{waga}] {tytul[:52]}")
    assert waga == oczekiwany, f"zła waga dla: {tytul}"

print("\n== Zapowiedź po terminie wypada z tablicy ==")
from kolektor.model import teraz
assert gminy._minela_data_w_tytule("uruchomienie syren w dniu 01.09.2026", teraz())
assert not gminy._minela_data_w_tytule("uruchomienie syren w dniu 31.12.2026", teraz())
assert not gminy._minela_data_w_tytule("Przerwa w dostawie wody", teraz())
print("   ✓ wpis z datą 01.09.2026 odrzucony, z 31.12.2026 zachowany")

print("\n== Nagłówek: same informacje nie dają ostrzeżenia ==")
from kolektor.render import przygotuj
from kolektor.model import StatusZrodla
status = StatusZrodla(id="gminy", nazwa="Gminy", ok=True,
                      pobrano=teraz().isoformat(timespec="seconds"))
tylko_info = [{"zrodlo": "gminy", "charakter": "zdarzenie", "typ": "Komunikat",
               "tytul": "Trening syren", "opis": "", "stopien": 0,
               "obowiazuje_od": None, "obowiazuje_do": None, "przestarzale": False,
               "wiek": None, "okres": ""}]
dane = przygotuj(list(tylko_info), [status], teraz())
print("   nagłówek:", dane["naglowek"], "| klasa:", dane["klasa_statusu"])
assert dane["naglowek"] == "Brak ostrzeżeń" and dane["klasa_statusu"] == "s0"

z_ostrzezeniem = tylko_info + [dict(tylko_info[0], tytul="Woda niezdatna do spożycia", stopien=2)]
dane = przygotuj(z_ostrzezeniem, [status], teraz())
print("   nagłówek:", dane["naglowek"], "| klasa:", dane["klasa_statusu"])
assert "2. stopnia" in dane["naglowek"] and "woda niezdatna" in dane["naglowek"]

print("\nKontrole wagi i nagłówka przeszły.")
