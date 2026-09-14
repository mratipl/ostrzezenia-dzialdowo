"""Ustawienia całego serwisu. Jedyne miejsce, które zmieniasz przy zmianie terenu."""

# --- Teren -------------------------------------------------------------
TERYT_POWIATU = "2803"          # powiat działdowski
NAZWA_POWIATU = "powiat działdowski"

# Środek powiatu (Działdowo) — do wyszukiwania najbliższych stacji i prognozy.
SZEROKOSC = 53.2373
DLUGOSC = 20.1806

# Promień, w jakim szukamy stacji pomiarowych GIOŚ (km).
# Zawężone z 60 km: przy tamtym promieniu na stronie pokazał się Ciechanów
# z odległości 48 km, czyli inny powiat i inne województwo. Odczyt z takiego
# dystansu nie mówi nic o powietrzu w Działdowie. Mława leży około 17 km,
# więc 30 km wystarcza, a resztę pokrywają czujniki Airly w powiecie.
PROMIEN_STACJI_KM = 30
MAKS_STACJI = 2

# Frazy wyłapujące utrudnienia istotne dla terenu z ogólnopolskiego pliku GDDKiA.
# Do skorygowania po pierwszym uruchomieniu, gdy zobaczysz realną treść wpisów.
FILTR_DROGOWY = [
    "warmińsko-mazursk",
    "warminsko-mazursk",
    "działdow",
    "dzialdow",
    "mława",
    "mlawa",
    "nidzic",
    "lidzbark",
]

# --- Airly -------------------------------------------------------------
# Klucz przekazuje się zmienną środowiskową AIRLY_KLUCZ (sekret w GitHubie).
# Identyfikator instalacji ustala się RAZ: python -m kolektor.main --airly
# i wpisuje poniżej. Powód jest twardy: limit 100 zapytań na dobę, a kolektor
# chodzi 72 razy — na szukanie instalacji w każdym cyklu nie ma budżetu.
# Wybrane czujniki: (identyfikator, etykieta na stronie).
# W powiecie stoi 17 instalacji, ale limit 100 zapytań na dobę pozwala na trzy
# przy odpytywaniu raz na godzinę. Wybór celowo pokrywa różny charakter terenu:
# centrum miasta, wieś pod miastem i drugą stronę powiatu.
# Pełną listę z odległościami daje: python -m kolektor.main --airly
AIRLY_INSTALACJE: list[tuple[int, str]] = [
    (10298, "Działdowo, Karłowicza"),
    (10286, "Lidzbark, Jeleńska"),
    (10291, "Płośnica, Kościelna"),
    (10288, "Rybno, Sportowa"),
    (10349, "Iłowo-Osada, Wyzwolenia"),
]
# Gmina Działdowo bez pokrycia — wszystkie trzy jej czujniki (Księży Dwór,
# Burkat, Uzdowo) nie działają. Otacza miasto z trzech stron, a czujnik
# miejski jest blisko, więc strata jest ograniczona.
#
# Nietestowane: Karłowicza, Płośnica, Rybno. Martwy czujnik jest odrzucany
# i raportowany ("3 z 5 — część niedostępna"), więc wymiana nie wymaga
# zgadywania — wystarczy spojrzeć na tabelę źródeł.

AIRLY_PROMIEN_KM = 30

# --- Scrapery HTML -----------------------------------------------------
# Frazy, po których rozpoznajemy, że komunikat dotyczy terenu. Szeroko,
# bo komunikaty wojewódzkie rzadko wymieniają powiat z nazwy.
FRAZY_TERENU = [
    "warmińsko-mazursk", "warminsko-mazursk", "warmii", "warmińsk",
    "działdow", "dzialdow", "lidzbark", "iłowo", "ilowo", "płośnic", "plosnic",
    "rybno", "nidzic", "mław", "mlaw",
    "całej polsce", "całego kraju", "cały kraj", "obszar kraju",
]

# Serwisy starostwa i gmin powiatu. Kolejność bez znaczenia.
GMINY: list[tuple[str, str]] = [
    ("Starostwo Działdowo", "https://powiatdzialdowski.pl/"),
    ("Miasto Działdowo", "https://www.dzialdowo.pl/"),
    ("Gmina Działdowo", "https://www.gminadzialdowo.pl/"),
    ("Gmina Lidzbark", "https://www.lidzbark.pl/"),
    ("Gmina Iłowo-Osada", "https://ilowo-osada.pl/"),
    ("Gmina Płośnica", "https://www.plosnica.pl/"),
    ("Gmina Rybno", "https://www.gminarybno.pl/"),
]

# Skrócone z 21 dni: zapowiedź treningu syren z 1 września trafiła do nagłówka
# 12 września jako "ostrzeżenie". Tablica ostrzegawcza ma pokazywać stan
# bieżący, nie archiwum.
GMINY_DNI_WSTECZ = 10

# Serwisy gmin to głównie treści niezwiązane z kryzysówką — dożynki, konkursy,
# inwestycje. Filtr jest tu ostrzejszy niż przy RCB: przepuszczamy tylko to,
# co ma znaczenie operacyjne albo dotyczy bezpieczeństwa mieszkańców.
# Słowa dzielone na trzy wagi. Wcześniej wszystkie wpisy gminne dostawały
# stopień 1, więc zapowiedź treningu syren wyglądała jak ostrzeżenie i trafiała
# do nagłówka strony. Zapowiedź czegoś zaplanowanego to informacja, awaria to
# utrudnienie, a dopiero zagrożenie zdrowia lub życia to ostrzeżenie.

# Wpisy odrzucane CAŁKOWICIE, jeszcze przed ważeniem.
#
# Powód: jubileusz 100-lecia OSP trafił do nagłówka jako "Ostrzeżenie
# 2. stopnia", bo "Ochotniczej Straży Pożarnej" zawiera słowo "pożar".
# Klasyczne fałszywe trafienie na rdzeniu wyrazu. Uroczystości, zawody
# i konkursy nie mają czego szukać na tablicy ostrzegawczej — nie wystarczy
# obniżyć im wagi, trzeba je usunąć.
SLOWA_WYKLUCZAJACE = [
    "jubileusz", "lecie", "uroczyst", "obchod", "święto", "swieto",
    "zawody", "turniej", "konkurs", "festiwal", "festyn", "piknik",
    "koncert", "wystaw", "dożynk", "dozynk", "wspólna historia",
    "gratulacj", "odznaczeni", "medal", "podziękowani", "życzeni",
    "przedszkol", "wycieczk", "warsztat", "spotkanie autorskie",
]

# Stopień 0 — informacja, nie wpływa na nagłówek.
# Te frazy rozstrzygają jako pierwsze: zapowiedź czegoś zaplanowanego jest
# informacją, nawet jeśli w treści pojawia się słowo o brzmieniu alarmowym.
SLOWA_ZAPOWIEDZI = [
    "trening", "ćwiczeni", "cwiczeni", "próbn", "probn", "planowan",
    "zapowiedź", "szkoleni", "kampani", "poradnik",
]

SLOWA_INFORMACYJNE = [
    "syren", "trening systemu", "trening wykrywani", "ćwiczeni obron",
    "ćwiczenia obron", "kwalifikacj wojskow", "obrona cywilna",
    "zarządzanie kryzysow", "kampani", "poradnik", "bądź gotowy",
    "próbny", "probny", "szkoleni",
]

# Stopień 1 — utrudnienie, realna niedogodność.
# Uwaga na odmianę: fraza "wyłączeni prądu" NIE pasuje do "wyłączenie prądu"
# ani "wyłączeniu prądu". Ten sam zestaw służy też jako filtr istotności, więc
# taka literówka wycinała komunikaty o wyłączeniach prądu z całej tablicy.
# Dlatego stosujemy rdzenie wyrazów, nie pełne formy.
SLOWA_UTRUDNIENIA = [
    "awari", "przerw", "brak wody", "brak prądu", "brak pradu",
    "wyłączen", "wylaczen", "bez prądu", "bez pradu",
    "utrudnieni", "objazd", "zamknięci", "zamkniet", "remont drogi",
    "wypadek", "kolizj", "zderzeni",
]

# Stopień 2 — ostrzeżenie: zagrożenie zdrowia, życia lub mienia.
# Uwaga: świadomie BEZ samego "alarm". To słowo występuje w "systemie
# wykrywania i alarmowania" oraz w "stopniu alarmowym", więc podnosiło
# zapowiedź treningu syren do rangi ostrzeżenia drugiego stopnia.
SLOWA_OSTRZEZENIA = [
    "ostrzeżeni", "ostrzega", "alert rcb", "zagrożeni", "alarm bombow",
    "woda niezdatna", "nieprzydatn do spożyci", "skażeni", "sinic",
    "zakaz kąpiel", "zakaz pobor", "ewakuacj",
    "pożar", "wichur", "burz", "podtopien", "powodz", "susz", "upał", "mróz",
    "asf", "ptasia gryp", "grypa ptak", "wścieklizn", "kwarantann",
    "stopień alarmow", "stopnie alarmow",
]

SLOWA_KRYZYSOWE = SLOWA_INFORMACYJNE + SLOWA_UTRUDNIENIA + SLOWA_OSTRZEZENIA

# --- Stopnie alarmowe --------------------------------------------------
# Wpisywane ręcznie i to jest świadoma decyzja, nie kapitulacja.
#
# Dlaczego nie automatycznie: gov.pl/web/rcb renderuje listę komunikatów
# skryptem, więc w surowym HTML-u nie ma czego parsować. Kanały RSS gmin
# pokazują kilkanaście najnowszych wpisów, a zarządzenia wychodzą raz na
# kwartał — po kilku tygodniach wpis wypada z kanału.
#
# Koszt aktualizacji: cztery razy w roku. Za to dane są pewne, bo przepisane
# wprost z zarządzenia, a nie odgadnięte z treści strony. Kolektor sam
# przypomni o przedłużeniu na 14 dni przed terminem.
#
# Źródło: gov.pl/web/rcb → komunikaty. Po przedłużeniu zmień OBOWIAZUJE_DO
# i w razie potrzeby listę.
STOPNIE_OBOWIAZUJA_DO = "2026-11-30T23:59:00"
STOPNIE_ALARMOWE: list[tuple[str, int, str]] = [
    ("CHARLIE", 2, "obszary linii kolejowych zarządzanych przez PKP PLK oraz PKP LHS"),
    ("BRAVO", 1, "cały obszar Rzeczypospolitej Polskiej"),
    ("BRAVO-CRP", 1, "cały obszar RP — cyberprzestrzeń"),
    ("BRAVO", 1, "polska infrastruktura energetyczna poza granicami RP"),
]

# Nazwa strefy prognostycznej zagrożenia pożarowego lasu.
LASY_STREFA = "Olsztyn"

# Źródła chwilowo wyłączone — nie będą odpytywane ani pokazywane.
# GDDKiA: plik XML zniknął po przeniesieniu serwisu na drogi.gddkia.gov.pl.
ZRODLA_WYLACZONE = [
    "gddkia",
    # gov.pl/web/rcb renderuje listę komunikatów skryptem — w surowym HTML-u
    # są tylko elementy nawigacji. Treści RCB i tak docierają przez serwisy
    # gmin, które je przepisują. Do włączenia, jeśli gov.pl kiedyś zacznie
    # serwować listę statycznie albo udostępni kanał RSS.
    "rcb",
    # Najbliższe stacje GIOŚ to Ciechanów (48 km) i Ostróda — w Mławie
    # czujnika nie ma. Z takiego dystansu odczyt nie opisuje powietrza
    # w powiecie, zwłaszcza w sezonie grzewczym, a kafelka "Dobry" brzmiałaby
    # jak zapewnienie. Warstwa powietrza opiera się na czujnikach Airly.
    "gios",
]

# --- Świeżość danych ---------------------------------------------------
# Po ilu minutach od ostatniego udanego pobrania źródło uznajemy za nieaktualne.
# Kafelka przechodzi wtedy w stan "BRAK DANYCH" — nigdy w "brak zagrożeń".
PROGI_SWIEZOSCI_MIN = {
    "imgw-meteo": 60,
    "imgw-hydro": 90,
    "imgw-synop": 120,
    "gios": 180,
    "airly": 120,
    "rcb": 90,
    "stopnie-alarmowe": 24 * 60,
    "lasy": 24 * 60,
    "pse": 180,
    "gminy": 180,
    "wlasne": 60,
    "open-meteo": 180,
    "gddkia": 120,
}
PROG_DOMYSLNY_MIN = 120

# Jak długo wolno przenosić dane z niedziałającego źródła.
#
# Przy awarii pokazujemy ostatnie znane informacje oznaczone szrafowaniem —
# to celowe, bo przy wichurze lepiej widzieć ostrzeżenie sprzed godziny niż
# pustą stronę. Ale bez górnej granicy odczyt przenosi się bez końca: po
# zawężeniu promienia stacji GIOŚ na tablicy została kafelka Ciechanowa,
# której źródło nigdy już nie odświeży. Po tym czasie pozycje znikają,
# a źródło zostaje oznaczone jako niedostępne.
MAKS_WIEK_PRZENOSZENIA_MIN = 360

# Minimalny odstęp między pobraniami danego źródła. Źródło odpytane niedawno
# jest pomijane, a jego poprzednie dane przenoszone jako aktualne — bez tego
# Airly wyczerpałoby dobowy limit przed południem.
MIN_ODSTEP_MIN = {
    # Pięć czujników przy odstępie 95 min daje realny cykl 100 min
    # (workflow chodzi co 20 min), czyli 14 pobrań na dobę: 14 × 5 = 70
    # zapytań przy limicie 100. Zapas 30 pokrywa błędy sieciowe i ręczne
    # sprawdzenia z przeglądarki.
    "airly": 95,
    # Stopnie alarmowe zmieniają się kwartalnie, a stopień zagrożenia
    # pożarowego raz na dobę. Odpytywanie ich co 20 minut to tylko obciążanie
    # cudzych serwerów bez żadnego zysku informacyjnego.
    "stopnie-alarmowe": 180,
    "lasy": 180,
    "rcb": 40,
    # Siedem serwisów po maksymalnie dwa żądania — nie ma powodu robić tego
    # częściej niż raz na godzinę.
    "gminy": 55,
}

# --- Sieć --------------------------------------------------------------
UA = (
    "OstrzezeniaDzialdowo/1.0 (prywatny serwis informacyjny; "
    "agregacja danych publicznych)"
)
TIMEOUT = 20
PROBY = 3

# --- Wyjście -----------------------------------------------------------
KATALOG_WYJSCIA = "public"
PLIK_STANU = "stan.json"        # commitowany do repo, przenosi stan między uruchomieniami

# Atrybucja wymagana regulaminami IMGW i GIOŚ.
ATRYBUCJA = [
    "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej "
    "– Państwowy Instytut Badawczy.",
    "Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu "
    "Badawczego zostały przetworzone.",
    "Dane o jakości powietrza: Główny Inspektorat Ochrony Środowiska, "
    "portal „Jakość Powietrza”.",
    "Dane o utrudnieniach na drogach krajowych: Generalna Dyrekcja Dróg "
    "Krajowych i Autostrad.",
]
