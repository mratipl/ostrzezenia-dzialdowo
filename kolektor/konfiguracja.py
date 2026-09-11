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

# --- Świeżość danych ---------------------------------------------------
# Po ilu minutach od ostatniego udanego pobrania źródło uznajemy za nieaktualne.
# Kafelka przechodzi wtedy w stan "BRAK DANYCH" — nigdy w "brak zagrożeń".
PROGI_SWIEZOSCI_MIN = {
    "imgw-meteo": 60,
    "imgw-hydro": 90,
    "imgw-synop": 120,
    "gios": 180,
    "open-meteo": 180,
    "gddkia": 120,
}
PROG_DOMYSLNY_MIN = 120

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
