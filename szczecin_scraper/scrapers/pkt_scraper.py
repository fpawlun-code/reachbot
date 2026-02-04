"""
Scraper dla PKT.pl (Polskie Książki Telefoniczne)

PKT.pl to tradycyjny katalog firm, często zawierający firmy
które nie są obecne w innych katalogach online.
"""
import logging
import re
from typing import Generator, Optional
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

BASE_URL = "https://www.pkt.pl"


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
    source: str = "pkt"
    has_website: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class PKTScraper:
    """Scraper dla PKT.pl."""

    def __init__(self):
        self.base_url = BASE_URL

    def search_businesses(
        self,
        industry: str,
        city: str = CITY,
        max_results: int = 50
    ) -> Generator[Business, None, None]:
        """
        Wyszukuje firmy w PKT.pl.

        Args:
            industry: Branża do wyszukania
            city: Miasto
            max_results: Maksymalna liczba wyników

        Yields:
            Business objects
        """
        logger.info(f"Searching PKT.pl: {industry} in {city}")

        # Buduj URL wyszukiwania
        # Format: https://www.pkt.pl/szukaj/restauracje/szczecin
        search_url = f"{self.base_url}/szukaj/{quote(industry)}/{city.lower()}"

        results_count = 0
        page = 1

        while results_count < max_results:
            url = search_url if page == 1 else f"{search_url}/strona/{page}"
            logger.info(f"Fetching: {url}")

            response = make_request(url)
            if not response:
                logger.warning(f"Failed to fetch page {page}")
                break

            soup = BeautifulSoup(response.text, "lxml")

            # Znajdź wyniki
            results = soup.select(
                "div.search-result-item, article.company, div.result-item, "
                "li.search-result, div[data-id]"
            )

            if not results:
                # Alternatywne selektory
                results = soup.select("div.company-box, div.firm-item")

            if not results:
                logger.info(f"No results found on page {page}")
                break

            for result in results:
                if results_count >= max_results:
                    break

                try:
                    business = self._parse_result(result, industry)
                    if business:
                        yield business
                        results_count += 1
                        random_delay(1, 2)

                except Exception as e:
                    logger.debug(f"Error parsing result: {e}")
                    continue

            # Sprawdź czy jest następna strona
            next_link = soup.select_one(
                "a.next, a[rel='next'], li.pagination-next a, a.pagination__next"
            )
            if not next_link:
                break

            page += 1
            random_delay(3, 5)

    def _parse_result(self, element, industry: str) -> Optional[Business]:
        """Parsuje pojedynczy wynik wyszukiwania."""
        try:
            # Nazwa firmy
            name_elem = element.select_one(
                "h2 a, h3 a, .company-name, .firm-name, a.title, .name a"
            )
            if not name_elem:
                name_elem = element.select_one("a[href*='/firma/']")

            if not name_elem:
                return None

            name = clean_text(name_elem.get_text())
            if not name:
                return None

            # Adres
            address = ""
            addr_elem = element.select_one(
                ".address, .location, .firma-address, span.street"
            )
            if addr_elem:
                address = clean_text(addr_elem.get_text())

            # Sprawdź czy adres zawiera miasto (Szczecin)
            city_elem = element.select_one(".city, .miasto")
            if city_elem:
                city_text = clean_text(city_elem.get_text())
                if city_text and city_text not in address:
                    address = f"{address}, {city_text}" if address else city_text

            # Telefon
            phone = ""
            phone_elem = element.select_one(
                ".phone, .tel, .telefon, a[href^='tel:']"
            )
            if phone_elem:
                phone = clean_text(phone_elem.get_text())
                if not phone:
                    phone = phone_elem.get("href", "").replace("tel:", "")

            # Usuń tekst "tel:" itp.
            phone = re.sub(r'^(tel\.?:?\s*)', '', phone, flags=re.IGNORECASE)

            # Email
            email = ""
            email_elem = element.select_one("a[href^='mailto:']")
            if email_elem:
                email = email_elem.get("href", "").replace("mailto:", "")

            # Strona www
            website = ""
            www_elem = element.select_one(
                "a.www, a.website, a[target='_blank'][href^='http']"
            )
            if www_elem:
                href = www_elem.get("href", "")
                if is_valid_website(href):
                    website = href

            # Sprawdź też tekst elementu
            if not website:
                text = element.get_text()
                www_match = re.search(r'www\.[a-z0-9.-]+\.[a-z]{2,}', text, re.IGNORECASE)
                if www_match:
                    potential_website = f"https://{www_match.group(0)}"
                    if is_valid_website(potential_website):
                        website = potential_website

            return Business(
                name=name,
                industry=industry,
                address=address,
                phone=phone,
                email=email,
                website=website,
                source="pkt",
                has_website=bool(website)
            )

        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None

    def get_business_details(self, profile_url: str, industry: str) -> Optional[Business]:
        """
        Pobiera szczegóły firmy ze strony profilu.

        Args:
            profile_url: URL strony profilu firmy
            industry: Branża

        Returns:
            Business object z pełnymi danymi
        """
        try:
            response = make_request(profile_url)
            if not response:
                return None

            soup = BeautifulSoup(response.text, "lxml")
            html = response.text

            # Nazwa
            name_elem = soup.select_one("h1, .company-name, .firma-name")
            name = clean_text(name_elem.get_text()) if name_elem else ""

            if not name:
                return None

            # Adres
            address = ""
            addr_elem = soup.select_one(
                "address, .address, [itemprop='address']"
            )
            if addr_elem:
                address = clean_text(addr_elem.get_text())

            # Telefon
            phones = extract_phones(html)
            phone = phones[0] if phones else ""

            # Email
            emails = extract_emails(html)
            email = emails[0] if emails else ""

            # Strona www
            website = ""
            www_elem = soup.select_one(
                "a[data-type='www'], a.website-link, a[rel='nofollow'][href^='http']"
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
                source="pkt",
                has_website=bool(website)
            )

        except Exception as e:
            logger.error(f"Error getting details from {profile_url}: {e}")
            return None
