# Ostrzeżenia — powiat działdowski

Prywatny, niekomercyjny agregator publicznych ostrzeżeń. Kolektor działa w GitHub
Actions, wynikiem jest statyczna strona wysyłana na InfinityFree.

Serwis nie jest urzędowym kanałem ostrzegania i nie jest prowadzony przez żaden urząd.

## Jak to działa

```
GitHub Actions (co 20 min)
  └─ python -m kolektor.main
       ├─ IMGW      ostrzeżenia meteorologiczne i hydrologiczne (filtr TERYT 2803)
       ├─ GIOŚ      indeks jakości powietrza z najbliższych stacji
       ├─ Open-Meteo prognoza na 24 h
       └─ GDDKiA    utrudnienia na drogach krajowych
  └─ public/index.html + public/dane.json
  └─ FTP → InfinityFree /htdocs/
```

Żadne źródło nie wymaga rejestracji ani klucza API.

## Dwie zasady wbudowane w kod

**Brak danych to nie brak zagrożeń.** Gdy źródło nie odpowie, serwis pokazuje
ostatnie znane informacje oznaczone ukośnym szrafowaniem i wiekiem danych, a na
górze wyświetla komunikat o nieudanym odświeżeniu. Nigdy nie wyświetli zielonego
„brak ostrzeżeń” dlatego, że nie udało się niczego pobrać. Ten scenariusz jest
objęty testem.

**Zdarzenia i stany to co innego.** Zdarzenie ma czas ważności i wygasa samo
(ostrzeżenie, utrudnienie). Stan obowiązuje do odwołania i nie miga (jakość
powietrza, prognoza). Mieszanie tych dwóch rzeczy czyni tablicę nieczytelną
po tygodniu.

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
python -m kolektor.main          # zbieranie na żywo → public/
python test_lokalny.py           # test na danych zastępczych, bez sieci
```

### Pierwszy krok: zobacz, co naprawdę zwracają API

IMGW publikuje adresy endpointów, ale nie schemat odpowiedzi. Parsery są
napisane tolerancyjnie (szukają pola po kilku kandydatach), więc powinny
zadziałać od razu — ale warto sprawdzić:

```bash
python -m kolektor.main --zrzut   # surowe odpowiedzi → diagnostyka/
```

Zajrzyj do `diagnostyka/imgw-meteo.txt` i porównaj nazwy pól z listą kandydatów
w `kolektor/zrodla/imgw.py`. Jeśli któreś się nie zgadza — dopisz właściwą nazwę
do wywołania `pole(...)`. To normalna kolejność pracy z niedokumentowanym API.

## Konfiguracja w GitHubie

Ustawienia → Secrets and variables → Actions → New repository secret:

| Nazwa | Wartość |
|---|---|
| `FTP_SERWER` | adres serwera FTP z panelu InfinityFree (zwykle `ftpupload.net`) |
| `FTP_UZYTKOWNIK` | login FTP, np. `if0_38xxxxxx` |
| `FTP_HASLO` | hasło FTP |
| `TOKEN_COMMIT` | token osobisty z uprawnieniem `repo` — patrz niżej |

`TOKEN_COMMIT` nie jest ozdobnikiem. Zaplanowane workflow są automatycznie
wyłączane po okresie bezczynności repozytorium, a commity robione domyślnym
tokenem nie resetują tego licznika. Bez tokena osobistego serwis po kilku
tygodniach po cichu przestanie się aktualizować. Jeśli token nie zostanie
ustawiony, workflow zadziała na `GITHUB_TOKEN` — wtedy zaglądaj do repozytorium
co jakiś czas.

## Zmiana terenu

Wszystko w `kolektor/konfiguracja.py`: kod TERYT powiatu, współrzędne środka,
promień szukania stacji, progi świeżości, frazy filtrujące utrudnienia drogowe.

## Cloudflare przed domeną

InfinityFree ma limit 50 000 odsłon na dobę, a każdy plik liczy się osobno.
Strona jest celowo jednoplikowa (style w środku, bez zewnętrznych fontów), więc
jedna wizyta to zasadniczo dwa trafienia. Przy realnym zdarzeniu ruch i tak
potrafi skoczyć o dwa rzędy wielkości — darmowy Cloudflare z cache na
`index.html` i `dane.json` ustawionym na 5 minut zdejmuje ten problem i przy
okazji rozwiązuje sprawę certyfikatu SSL.

## Co dalej

Źródła wymagające parsowania HTML, świadomie odłożone do drugiego etapu:
komunikaty RCB, stopnie alarmowe, wyłączenia prądu Energi, komunikaty PSSE,
stopień zagrożenia pożarowego lasu, stopnie zasilania PSE. Dokładamy je jako
kolejne moduły w `kolektor/zrodla/` — rdzeń nie wymaga wtedy zmian.

## Źródła i atrybucja

Wymagane noty są renderowane w stopce strony. Dane IMGW-PIB są wykorzystywane
do celów prywatnych i niekomercyjnych; serwis nie zawiera reklam ani treści
o charakterze gospodarczym.
