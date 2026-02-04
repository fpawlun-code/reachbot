"""
Google Maps / Places API Scraper

Ten moduł używa oficjalnego Google Places API do wyszukiwania firm.
API jest płatne, ale oferuje darmowy limit ~$200/miesiąc.

Alternatywnie, zawiera też wersję z Selenium do scrapowania bez API.
"""
import logging
import time
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass, asdict

try:
    import googlemaps
    GOOGLEMAPS_AVAILABLE = True
except ImportError:
    GOOGLEMAPS_AVAILABLE = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from config import GOOGLE_MAPS_API_KEY, CITY, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from utils.helpers import random_delay, clean_text
from utils.validators import extract_emails, extract_phones, extract_social_media

logger = logging.getLogger(__name__)


@dataclass
class Business:
    """Reprezentacja firmy."""
    name: str
    industry: str
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    facebook: str = ""
    instagram: str = ""
    linkedin: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    source: str = ""
    has_website: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class GoogleMapsScraper:
    """
    Scraper firm z Google Maps.

    Dwa tryby działania:
    1. API Mode (zalecany) - używa oficjalnego Google Places API
    2. Selenium Mode - scrapuje bezpośrednio stronę (ryzyko blokad)
    """

    def __init__(self, use_api: bool = True):
        """
        Inicjalizuje scraper.

        Args:
            use_api: Czy użyć Google Places API (wymaga klucza)
        """
        self.use_api = use_api and GOOGLE_MAPS_API_KEY and GOOGLEMAPS_AVAILABLE
        self.client = None
        self.driver = None

        if self.use_api:
            try:
                self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
                logger.info("Google Maps API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google Maps API: {e}")
                self.use_api = False

    def search_businesses(
        self,
        industry: str,
        city: str = CITY,
        max_results: int = 20
    ) -> Generator[Business, None, None]:
        """
        Wyszukuje firmy danej branży w mieście.

        Args:
            industry: Branża (np. "restauracje", "kancelarie prawne")
            city: Miasto do przeszukania
            max_results: Maksymalna liczba wyników

        Yields:
            Business objects
        """
        query = f"{industry} {city}"
        logger.info(f"Searching: {query}")

        if self.use_api:
            yield from self._search_with_api(query, max_results)
        else:
            yield from self._search_with_selenium(query, max_results)

    def _search_with_api(
        self,
        query: str,
        max_results: int
    ) -> Generator[Business, None, None]:
        """Wyszukiwanie przez Google Places API."""
        try:
            results_count = 0
            next_page_token = None

            while results_count < max_results:
                # Text search
                if next_page_token:
                    time.sleep(2)  # API wymaga przerwy przed użyciem tokena
                    response = self.client.places(
                        query=query,
                        page_token=next_page_token
                    )
                else:
                    response = self.client.places(query=query)

                places = response.get('results', [])

                for place in places:
                    if results_count >= max_results:
                        break

                    # Pobierz szczegóły miejsca
                    business = self._get_place_details(place)
                    if business:
                        yield business
                        results_count += 1
                        random_delay(0.5, 1)  # Mniejsze opóźnienie dla API

                # Sprawdź czy jest następna strona
                next_page_token = response.get('next_page_token')
                if not next_page_token:
                    break

        except Exception as e:
            logger.error(f"API search error: {e}")

    def _get_place_details(self, place: dict) -> Optional[Business]:
        """Pobiera szczegóły miejsca z API."""
        try:
            place_id = place.get('place_id')
            if not place_id:
                return None

            # Pobierz pełne szczegóły
            details = self.client.place(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'website', 'rating', 'user_ratings_total', 'types'
                ]
            )

            result = details.get('result', {})

            # Określ branżę na podstawie types
            types = result.get('types', [])
            industry = self._types_to_industry(types)

            return Business(
                name=result.get('name', ''),
                industry=industry,
                address=result.get('formatted_address', ''),
                phone=result.get('formatted_phone_number', ''),
                website=result.get('website', ''),
                rating=result.get('rating', 0.0),
                reviews_count=result.get('user_ratings_total', 0),
                source='google_maps_api',
                has_website=bool(result.get('website'))
            )

        except Exception as e:
            logger.error(f"Error getting place details: {e}")
            return None

    def _types_to_industry(self, types: List[str]) -> str:
        """Konwertuje Google Place types na branżę."""
        type_mapping = {
            'restaurant': 'Restauracja',
            'cafe': 'Kawiarnia',
            'lawyer': 'Kancelaria prawna',
            'hair_care': 'Fryzjer',
            'beauty_salon': 'Salon kosmetyczny',
            'car_repair': 'Mechanik samochodowy',
            'dentist': 'Dentysta',
            'veterinary_care': 'Weterynarz',
            'bakery': 'Piekarnia',
            'florist': 'Kwiaciarnia',
            'accounting': 'Biuro rachunkowe',
            'real_estate_agency': 'Agencja nieruchomości',
            'electrician': 'Elektryk',
            'plumber': 'Hydraulik',
        }

        for t in types:
            if t in type_mapping:
                return type_mapping[t]
        return types[0] if types else 'Inne'

    def _search_with_selenium(
        self,
        query: str,
        max_results: int
    ) -> Generator[Business, None, None]:
        """
        Wyszukiwanie przez Selenium (scrapowanie strony).
        Używać ostrożnie - ryzyko blokady!
        """
        if not self.driver:
            self._init_selenium()

        try:
            # Otwórz Google Maps
            self.driver.get("https://www.google.pl/maps")
            random_delay(2, 4)

            # Zaakceptuj cookies jeśli potrzeba
            try:
                accept_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Zaakceptuj')]"))
                )
                accept_btn.click()
                random_delay(1, 2)
            except TimeoutException:
                pass

            # Wyszukaj
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "searchboxinput"))
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.ENTER)
            random_delay(3, 5)

            # Scrolluj wyniki i zbieraj dane
            results_count = 0
            processed_names = set()

            # Znajdź kontener z wynikami
            results_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']"))
            )

            while results_count < max_results:
                # Scrolluj w dół
                self.driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight",
                    results_container
                )
                random_delay(2, 3)

                # Znajdź wszystkie wyniki
                results = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[role='feed'] > div > div > a"
                )

                for result in results:
                    if results_count >= max_results:
                        break

                    try:
                        name = result.get_attribute("aria-label")
                        if not name or name in processed_names:
                            continue

                        processed_names.add(name)

                        # Kliknij aby zobaczyć szczegóły
                        result.click()
                        random_delay(2, 3)

                        # Pobierz szczegóły
                        business = self._extract_business_from_page(name, query)
                        if business:
                            yield business
                            results_count += 1

                    except Exception as e:
                        logger.debug(f"Error processing result: {e}")
                        continue

                # Sprawdź czy są jeszcze wyniki do załadowania
                if len(results) == len(processed_names):
                    break

        except Exception as e:
            logger.error(f"Selenium search error: {e}")

    def _extract_business_from_page(self, name: str, query: str) -> Optional[Business]:
        """Wyciąga dane firmy z otwartej strony szczegółów w Google Maps."""
        try:
            # Pobierz adres
            address = ""
            try:
                address_elem = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "button[data-item-id='address']"
                )
                address = address_elem.text
            except NoSuchElementException:
                pass

            # Pobierz telefon
            phone = ""
            try:
                phone_elem = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "button[data-item-id^='phone']"
                )
                phone = phone_elem.text
            except NoSuchElementException:
                pass

            # Pobierz stronę www
            website = ""
            try:
                website_elem = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "a[data-item-id='authority']"
                )
                website = website_elem.get_attribute("href")
            except NoSuchElementException:
                pass

            # Określ branżę z query
            industry = query.split()[0] if query else "Inne"

            return Business(
                name=clean_text(name),
                industry=industry,
                address=clean_text(address),
                phone=clean_text(phone),
                website=website,
                source='google_maps_selenium',
                has_website=bool(website)
            )

        except Exception as e:
            logger.error(f"Error extracting business details: {e}")
            return None

    def _init_selenium(self):
        """Inicjalizuje Selenium WebDriver."""
        options = Options()
        options.add_argument("--headless")  # Tryb bez okna
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=pl-PL")

        # Ukryj że to automatyzacja
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        # Ukryj webdriver
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def close(self):
        """Zamyka zasoby."""
        if self.driver:
            self.driver.quit()
            self.driver = None
