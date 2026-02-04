"""
Scraper dla Panorama Firm (panoramafirm.pl)

Panorama Firm to jeden z największych katalogów firm w Polsce.
Zawiera dane kontaktowe, adresy, i często informację o stronie www.
"""
import logging
import re
from typing import Generator, Optional, List
from urllib.parse import urljoin, quote
from dataclasses import dataclass, asdict

from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from config import CITY
from utils.helpers import make_request, random_delay, clean_text
from utils.validators import (
    extract_emails, extract_phones, extract_social_media,
    is_valid_website
)

logger = logging.getLogger(__name__)

BASE_URL = "https://panoramafirm.pl"


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
    source: str = "panorama_firm"
    has_website: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class PanoramaFirmScraper:
    """Scraper dla Panorama Firm."""

    def __init__(self):
        self.base_url = BASE_URL
        self.session_cookies = {}

    def search_businesses(
        self,
        industry: str,
        city: str = CITY,
        max_results: int = 50
    ) -> Generator[Business, None, None]:
        """
        Wyszukuje firmy w Panorama Firm.

        Args:
            industry: Branża do wyszukania
            city: Miasto
            max_results: Maksymalna liczba wyników

        Yields:
            Business objects
        """
        logger.info(f"Searching Panorama Firm: {industry} in {city}")

        # Użyj URL kategorii zamiast wyszukiwarki (lepsza struktura)
        # Format: https://panoramafirm.pl/restauracje/szczecin
        category_url = f"{self.base_url}/{quote(industry)}/{city.lower()}"

        results_count = 0
        page = 1

        while results_count < max_results:
            url = category_url if page == 1 else f"{category_url},{page}"
            logger.info(f"Fetching page {page}: {url}")

            response = make_request(url)
            if not response:
                logger.warning(f"Failed to fetch page {page}")
                break

            soup = BeautifulSoup(response.text, "lxml")
            html = response.text

            # Nowa struktura - szukaj linków do firm
            # Klasa: addax-cs_hl_hit_company_name_click
            results = soup.select("a.addax-cs_hl_hit_company_name_click")

            if not results:
                # Alternatywnie - szukaj wszystkich linków do /firma/
                results = soup.select("a[href*='/firma/']")

            if not results:
                # Ostatnia próba - szukaj w article/div
                results = soup.select("article a[href*='panoramafirm.pl'], div.company a")

            if not results:
                logger.info(f"No results on page {page}")
                break

            for link in results:
                if results_count >= max_results:
                    break

                try:
                    href = link.get("href", "")
                    name = clean_text(link.get_text())

                    if not name or not href:
                        continue

                    # Pełny URL
                    if not href.startswith("http"):
                        href = urljoin(self.base_url, href)

                    # Pobierz szczegóły ze strony firmy
                    business = self._fetch_company_details(href, name, industry)
                    if business:
                        yield business
                        results_count += 1
                        logger.debug(f"  + {name}")
                        random_delay(2, 4)

                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue

            # Sprawdź paginację - szukaj linku do następnej strony
            next_link = soup.select_one("a[rel='next'], a:contains('Następna'), a:contains('›')")
            if not next_link and page < 5:  # Max 5 stron
                # Spróbuj następnej strony
                page += 1
                random_delay(3, 5)
            elif next_link:
                page += 1
                random_delay(3, 5)
            else:
                break

    def _fetch_company_details(
        self,
        url: str,
        name: str,
        industry: str
    ) -> Optional[Business]:
        """Pobiera szczegóły firmy z jej strony profilu."""
        try:
            response = make_request(url)
            if not response:
                return Business(name=name, industry=industry, source="panorama_firm")

            soup = BeautifulSoup(response.text, "lxml")
            html = response.text

            # Adres
            address = ""
            addr_elem = soup.select_one(
                "[itemprop='address'], .address, address"
            )
            if addr_elem:
                address = clean_text(addr_elem.get_text())

            # Telefon
            phone = ""
            phone_elem = soup.select_one(
                "a[href^='tel:'], [itemprop='telephone']"
            )
            if phone_elem:
                phone = phone_elem.get("href", "").replace("tel:", "")
                if not phone:
                    phone = clean_text(phone_elem.get_text())

            # Alternatywnie - wyciągnij z tekstu
            if not phone:
                phones = extract_phones(html)
                if phones:
                    phone = phones[0]

            # Email
            email = ""
            email_elem = soup.select_one("a[href^='mailto:']")
            if email_elem:
                email = email_elem.get("href", "").replace("mailto:", "")

            if not email:
                emails = extract_emails(html)
                if emails:
                    email = emails[0]

            # Strona www
            website = ""
            www_elem = soup.select_one(
                "a[data-stat-id='www'], a.website, a[rel='nofollow'][href^='http']"
            )
            if www_elem:
                href = www_elem.get("href", "")
                if is_valid_website(href):
                    website = href

            # Social media
            social = extract_social_media(html)

            return Business(
                name=name,
                industry=industry,
                address=address,
                phone=phone,
                email=email,
                website=website,
                facebook=social.get("facebook", ""),
                instagram=social.get("instagram", ""),
                linkedin=social.get("linkedin", ""),
                source="panorama_firm",
                has_website=bool(website)
            )

        except Exception as e:
            logger.debug(f"Error fetching details for {name}: {e}")
            return Business(name=name, industry=industry, source="panorama_firm")

    def _parse_search_result(self, element, industry: str) -> Optional[Business]:
        """Parsuje pojedynczy wynik wyszukiwania."""
        try:
            # Nazwa firmy
            name_elem = element.select_one(
                "h2 a, h3 a, .company-name a, .name a, a[title]"
            )
            if not name_elem:
                return None

            name = clean_text(name_elem.get_text())
            if not name:
                return None

            # Link do strony firmy w katalogu
            detail_url = name_elem.get("href", "")
            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin(self.base_url, detail_url)

            # Adres
            address = ""
            addr_elem = element.select_one(
                ".address, .company-address, span[itemprop='address'], .location"
            )
            if addr_elem:
                address = clean_text(addr_elem.get_text())

            # Telefon
            phone = ""
            phone_elem = element.select_one(
                ".phone, .tel, a[href^='tel:'], span[itemprop='telephone']"
            )
            if phone_elem:
                phone = clean_text(phone_elem.get_text())
                if not phone:
                    phone = phone_elem.get("href", "").replace("tel:", "")

            # Strona www
            website = ""
            www_elem = element.select_one(
                "a.website, a.www, a[href*='http']:not([href*='panoramafirm'])"
            )
            if www_elem:
                href = www_elem.get("href", "")
                if is_valid_website(href):
                    website = href

            # Email
            email = ""
            email_elem = element.select_one("a[href^='mailto:']")
            if email_elem:
                email = email_elem.get("href", "").replace("mailto:", "")

            return Business(
                name=name,
                industry=industry,
                address=address,
                phone=phone,
                email=email,
                website=website,
                source="panorama_firm",
                has_website=bool(website)
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def _get_business_details(self, business: Business) -> Optional[Business]:
        """
        Pobiera szczegółowe dane firmy ze strony profilu.

        Args:
            business: Obiekt Business z podstawowymi danymi

        Returns:
            Business z uzupełnionymi danymi
        """
        try:
            # Szukaj strony profilu
            search_url = f"{self.base_url}/{quote(business.name.lower().replace(' ', '-'))}"

            response = make_request(search_url)
            if not response:
                return business

            soup = BeautifulSoup(response.text, "lxml")
            html = response.text

            # Uzupełnij brakujące dane

            # Email
            if not business.email:
                emails = extract_emails(html)
                if emails:
                    business.email = emails[0]

            # Telefon
            if not business.phone:
                phones = extract_phones(html)
                if phones:
                    business.phone = phones[0]

            # Strona www
            if not business.website:
                www_elem = soup.select_one(
                    "a[data-stat-id='www'], a.company-www, a[rel='nofollow'][href^='http']"
                )
                if www_elem:
                    href = www_elem.get("href", "")
                    if is_valid_website(href):
                        business.website = href
                        business.has_website = True

            # Social media
            social = extract_social_media(html)
            if not business.facebook and social.get("facebook"):
                business.facebook = social["facebook"]
            if not business.instagram and social.get("instagram"):
                business.instagram = social["instagram"]
            if not business.linkedin and social.get("linkedin"):
                business.linkedin = social["linkedin"]

            # Adres (jeśli brakuje)
            if not business.address:
                addr_elem = soup.select_one(
                    "address, .address, span[itemprop='streetAddress']"
                )
                if addr_elem:
                    business.address = clean_text(addr_elem.get_text())

            return business

        except Exception as e:
            logger.debug(f"Error getting details: {e}")
            return business

    def get_businesses_by_category(
        self,
        category_slug: str,
        city: str = CITY,
        max_results: int = 50
    ) -> Generator[Business, None, None]:
        """
        Pobiera firmy z konkretnej kategorii.

        Args:
            category_slug: Slug kategorii (np. "restauracje", "prawnicy")
            city: Miasto
            max_results: Maksymalna liczba wyników

        Yields:
            Business objects
        """
        # URL kategorii: https://panoramafirm.pl/restauracje/szczecin
        category_url = f"{self.base_url}/{category_slug}/{city.lower()}"

        logger.info(f"Fetching category: {category_url}")

        results_count = 0
        page = 1

        while results_count < max_results:
            url = f"{category_url}" if page == 1 else f"{category_url},{page}"

            response = make_request(url)
            if not response:
                break

            soup = BeautifulSoup(response.text, "lxml")

            # Znajdź firmy
            companies = soup.select(
                "div.company-item, article.item, div[itemtype*='LocalBusiness']"
            )

            if not companies:
                break

            for company in companies:
                if results_count >= max_results:
                    break

                business = self._parse_search_result(company, category_slug)
                if business:
                    yield business
                    results_count += 1
                    random_delay(1, 2)

            page += 1
            random_delay(3, 5)
