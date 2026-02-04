# Szczecin Business Scraper

Bot do skanowania rynku w Szczecinie w poszukiwaniu firm, które nie posiadają własnej strony internetowej. Idealne narzędzie do generowania leadów dla agencji web development.

## Funkcje

- **Skanowanie wielu źródeł**: Panorama Firm, PKT.pl, Google Maps (opcjonalnie)
- **Filtrowanie firm bez WWW**: Automatyczna weryfikacja czy firma ma działającą stronę
- **Zbieranie danych kontaktowych**: Email, telefon, social media, adres
- **Eksport do wielu formatów**: Excel (XLSX), CSV, Word (DOCX), JSON
- **Generator wiadomości**: Szablony emaili, DM na Instagram/Facebook/LinkedIn
- **Ochrona przed blokadami**: Rate limiting, rotacja User-Agent, obsługa proxy

## Struktura projektu

```
szczecin_scraper/
├── main.py                 # Główny skrypt CLI
├── config.py               # Konfiguracja
├── requirements.txt        # Zależności Python
├── .env.example           # Przykładowa konfiguracja
├── scrapers/
│   ├── google_maps.py     # Scraper Google Maps/Places API
│   ├── panorama_firm.py   # Scraper Panorama Firm
│   ├── pkt_scraper.py     # Scraper PKT.pl
│   └── website_checker.py # Weryfikacja stron WWW
├── utils/
│   ├── helpers.py         # Funkcje pomocnicze
│   ├── validators.py      # Walidacja danych
│   └── exporter.py        # Eksport do plików
├── templates/
│   └── messages.py        # Szablony wiadomości
└── output/                # Katalog z wynikami
```

## Instalacja

### 1. Wymagania

- Python 3.9+
- Chrome/Chromium (dla Selenium)
- Opcjonalnie: Google Maps API key

### 2. Klonowanie i setup

```bash
# Przejdź do katalogu projektu
cd szczecin_scraper

# Utwórz wirtualne środowisko
python -m venv venv

# Aktywuj środowisko
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Zainstaluj zależności
pip install -r requirements.txt
```

### 3. Konfiguracja

```bash
# Skopiuj przykładową konfigurację
cp .env.example .env

# Edytuj plik .env
nano .env  # lub użyj dowolnego edytora
```

Dostępne opcje w `.env`:

```env
# Google Maps API (opcjonalne, ale zalecane)
GOOGLE_MAPS_API_KEY=twoj_klucz_api

# Opóźnienia między requestami (sekundy)
REQUEST_DELAY_MIN=2
REQUEST_DELAY_MAX=5

# Maksymalna liczba firm
MAX_BUSINESSES=100

# Branże do skanowania
INDUSTRIES=restauracje,kawiarnie,kancelarie prawne,fryzjerzy

# Format eksportu: csv, xlsx, docx
OUTPUT_FORMAT=xlsx
```

## Użycie

### Podstawowe skanowanie

```bash
# Pełne skanowanie wszystkich branż
python main.py

# Skanowanie wybranych branż
python main.py --industries restauracje kawiarnie "kancelarie prawne"

# Ograniczenie wyników
python main.py --max-results 30

# Eksport do Word
python main.py --output-format docx

# Szybkie skanowanie (bez weryfikacji stron)
python main.py --no-verify

# Szczegółowe logi
python main.py --verbose
```

### Przykłady zaawansowane

```bash
# Tylko Panorama Firm, 50 wyników na branżę
python main.py --sources panorama --max-results 50

# Skanuj restauracje i kawiarnie, eksportuj do CSV
python main.py -i restauracje kawiarnie -f csv

# Z Google Maps API (wymaga klucza)
python main.py --sources google panorama pkt
```

### Generowanie wiadomości

```python
from templates.messages import MessageGenerator

# Inicjalizuj generator z Twoimi danymi
generator = MessageGenerator(
    sender_name="Jan Kowalski",
    sender_company="MojaFirma Web",
    sender_email="jan@mojafirma.pl",
    sender_phone="+48 500 100 200",
    sender_website="https://mojafirma.pl"
)

# Wygeneruj wiadomości dla firmy
business = {
    "name": "Restauracja Pod Lipą",
    "industry": "Restauracje",
    "email": "kontakt@podlipa.pl",
    "facebook": "https://facebook.com/podlipa"
}

messages = generator.generate_all_messages(business)
print(messages["email"]["body"])
print(messages["instagram"])
```

## Wyniki

Po skanowaniu w katalogu `output/` znajdziesz:

- `firmy_szczecin_YYYYMMDD_HHMMSS.xlsx` - główny plik z danymi
- `podsumowanie_YYYYMMDD_HHMMSS.txt` - statystyki skanowania
- `scraper.log` - logi działania

### Format danych

| Kolumna | Opis |
|---------|------|
| Nazwa firmy | Pełna nazwa |
| Branża | Kategoria działalności |
| Adres | Adres siedziby |
| Telefon | Numer kontaktowy |
| Email | Adres email |
| Facebook | Link do profilu FB |
| Instagram | Link do profilu IG |
| LinkedIn | Link do profilu LI |
| Strona WWW | URL strony (jeśli jest) |
| Ma stronę? | Tak/Nie |
| Źródło | Skąd pochodzi lead |

## Ograniczenia i best practices

### Rate Limiting

Bot automatycznie dodaje opóźnienia między requestami, aby uniknąć blokad:

- Domyślnie: 2-5 sekund między requestami
- Przy rate limit (429): 30 sekund przerwy
- Między stronami wyników: 3-6 sekund

### Unikanie blokad

1. **Nie skanuj zbyt intensywnie** - ustaw rozsądne limity
2. **Używaj proxy** (opcjonalnie) - skonfiguruj w `.env`
3. **Rotuj User-Agent** - bot robi to automatycznie
4. **Skanuj w różnych porach** - rozłóż skanowanie w czasie

### Google Maps API

- Darmowy limit: ~$200/miesiąc (~28,000 requestów)
- Koszt powyżej limitu: $0.007/request
- Zalecane dla większych skanowań

Uzyskaj klucz: https://console.cloud.google.com/apis/credentials

## Aspekty prawne

**WAŻNE**: Przed użyciem upewnij się, że:

1. Scrapowanie jest zgodne z regulaminami stron źródłowych
2. Przetwarzanie danych jest zgodne z RODO
3. Wysyłanie wiadomości marketingowych jest zgodne z przepisami
4. Masz podstawę prawną do kontaktu (uzasadniony interes)

Dane publicznie dostępne w katalogach firm są zazwyczaj przeznaczone do kontaktu biznesowego, ale zachowaj ostrożność i profesjonalizm.

## Rozwiązywanie problemów

### "No module named 'xxx'"

```bash
pip install -r requirements.txt
```

### "Chrome not found"

```bash
# Ubuntu/Debian
sudo apt install chromium-browser

# Mac
brew install --cask chromium
```

### Rate limit / Blocked

- Zwiększ `REQUEST_DELAY_MIN` i `REQUEST_DELAY_MAX` w `.env`
- Użyj proxy
- Poczekaj kilka godzin przed ponownym skanowaniem

### Brak wyników

- Sprawdź pisownię branży
- Spróbuj innych źródeł (`--sources panorama pkt`)
- Użyj `--verbose` dla szczegółowych logów

## Licencja

Projekt do użytku osobistego i edukacyjnego. Używaj odpowiedzialnie.

## Kontakt

Problemy? Otwórz issue na GitHubie.
