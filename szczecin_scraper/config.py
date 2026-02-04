"""
Konfiguracja Szczecin Business Scraper
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Ładuj zmienne środowiskowe
load_dotenv()

# Ścieżki
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Ustawienia requestów
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", 2))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", 5))
MAX_BUSINESSES = int(os.getenv("MAX_BUSINESSES", 100))

# Lokalizacja
CITY = os.getenv("CITY", "Szczecin")
COUNTRY = os.getenv("COUNTRY", "Polska")

# Branże do skanowania
DEFAULT_INDUSTRIES = [
    "restauracje",
    "kawiarnie",
    "kancelarie prawne",
    "doradcy prawni",
    "fryzjerzy",
    "salony kosmetyczne",
    "mechanicy samochodowi",
    "dentyści",
    "weterynarze",
    "piekarnie",
    "kwiaciarnie",
    "fotografowie",
    "biura rachunkowe",
    "agencje nieruchomości",
    "firmy sprzątające",
    "usługi remontowe",
    "elektrycy",
    "hydraulicy",
]

INDUSTRIES = os.getenv("INDUSTRIES", ",".join(DEFAULT_INDUSTRIES)).split(",")
INDUSTRIES = [i.strip() for i in INDUSTRIES if i.strip()]

# Eksport
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "xlsx")

# User agents dla web scrapingu
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Katalogi firm do scrapowania
BUSINESS_DIRECTORIES = {
    "panorama_firm": "https://panoramafirm.pl",
    "pkt": "https://www.pkt.pl",
    "aleo": "https://aleo.com",
    "gowork": "https://www.gowork.pl",
}

# Wzorce do wykrywania braku strony internetowej
NO_WEBSITE_INDICATORS = [
    "brak strony",
    "brak www",
    "nie posiada strony",
    "strona niedostępna",
]

# Proxy (opcjonalne)
USE_PROXY = os.getenv("USE_PROXY", "false").lower() == "true"
PROXY_URL = os.getenv("PROXY_URL", "")
