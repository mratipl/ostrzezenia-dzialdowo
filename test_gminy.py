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

STRONA_BEZ_RSS = """
<html><body><ul>
 <li><a href="/a">Ostrzeżenie o silnym wiatrze dla gminy</a>
     <p>Prosimy o zachowanie ostrożności, 11 września 2026.</p></li>
 <li><a href="/b">Nowy plac zabaw otwarty</a><p>Uroczyste otwarcie placu zabaw.</p></li>
 <li><a href="/c">Zebranie wiejskie w sprawie funduszu</a><p>Porządek obrad zebrania.</p></li>
</ul></body></html>
"""

def fałszywy(url, naglowki=None, proby=None, zapasowy_ua=True):
    if "feed" in url:
        return KANAL
    if "plosnica" in url or "gminarybno" in url:
        return STRONA_BEZ_RSS
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
