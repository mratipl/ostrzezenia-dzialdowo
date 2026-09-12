"""Ustawienia całego serwisu. Jedyne miejsce, które zmieniasz przy zmianie terenu."""

# --- Teren -------------------------------------------------------------
TERYT_POWIATU = "2803"          # powiat działdowski
NAZWA_POWIATU = "powiat działdowski"

# Środek powiatu (Działdowo) — do wyszukiwania najbliższych stacji i prognozy.
SZEROKOSC = 53.2373
DLUGOSC = 20.1806

# Promień, w jakim szukamy stacji pomiarowych GIOŚ (km).
PROMIEN_STACJI_KM = 60
MAKS_STACJI = 3

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
    (10303, "Działdowo, Plac Mickiewicza"),
    (10343, "Księży Dwór"),
    (10349, "Iłowo-Osada, Wyzwolenia"),
]
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

GMINY_DNI_WSTECZ = 21

# Serwisy gmin to głównie treści niezwiązane z kryzysówką — dożynki, konkursy,
# inwestycje. Filtr jest tu ostrzejszy niż przy RCB: przepuszczamy tylko to,
# co ma znaczenie operacyjne albo dotyczy bezpieczeństwa mieszkańców.
SLOWA_KRYZYSOWE = [
    "ostrzeżeni", "ostrzega", "alarm", "alert", "zagrożeni",
    "awari", "przerw w dostaw", "przerwa w dostaw", "brak wody", "wyłączeni prądu",
    "wyłączenia prądu", "bez prądu", "jakość wody", "woda niezdatna", "skażeni",
    "syren", "trening systemu", "ćwiczeni obron", "ewakuacj",
    "pożar", "wichur", "burz", "podtopien", "powodz", "susz", "upał", "mróz",
    "asf", "ptasia gryp", "grypa ptak", "wścieklizn", "kwarantann",
    "zakaz", "utrudnieni", "objazd", "zamknięci drogi", "zamknięcie drogi",
    "wypadek", "kolizj", "zarządzanie kryzysow", "obrona cywilna",
    "stopień alarmow", "stopnie alarmow", "rcb",
]

# Nazwa strefy prognostycznej zagrożenia pożarowego lasu.
LASY_STREFA = "Olsztyn"

# Źródła chwilowo wyłączone — nie będą odpytywane ani pokazywane.
# GDDKiA: plik XML zniknął po przeniesieniu serwisu na drogi.gddkia.gov.pl.
ZRODLA_WYLACZONE = ["gddkia"]

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

# Minimalny odstęp między pobraniami danego źródła. Źródło odpytane niedawno
# jest pomijane, a jego poprzednie dane przenoszone jako aktualne — bez tego
# Airly wyczerpałoby dobowy limit przed południem.
MIN_ODSTEP_MIN = {
    "airly": 55,
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
