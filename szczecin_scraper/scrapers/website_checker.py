"""
Moduł do weryfikacji stron internetowych firm.

Sprawdza czy podany URL faktycznie prowadzi do działającej strony
i czy jest to prawdziwa strona firmowa (a nie social media czy katalog).
"""
import logging
import re
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass
import socket

import requests

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from utils.helpers import make_request, get_headers
from utils.validators import (
    is_valid_website, extract_emails, extract_phones, extract_social_media
)

logger = logging.getLogger(__name__)


@dataclass
class WebsiteStatus:
    """Status sprawdzenia strony internetowej."""
    url: str
    exists: bool
    is_active: bool
    is_company_site: bool
    status_code: int = 0
    redirect_url: str = ""
    error: str = ""


class WebsiteChecker:
    """
    Sprawdza status stron internetowych firm.

    Funkcje:
    - Weryfikacja czy strona istnieje i działa
    - Wykrywanie przekierowań (np. na parking domenowy)
    - Sprawdzanie czy to prawdziwa strona firmowa
    - Wyciąganie dodatkowych kontaktów ze strony
    """

    # Wzorce wskazujące na parking domenowy lub nieaktywną stronę
    PARKING_PATTERNS = [
        r"domain.*parking",
        r"domain.*sale",
        r"domain.*for\s*sale",
        r"buy\s*this\s*domain",
        r"this\s*domain.*available",
        r"domena.*sprzedaż",
        r"domena.*do\s*kupienia",
        r"strona\s*w\s*budowie",
        r"under\s*construction",
        r"coming\s*soon",
        r"wkrótce",
        r"hostinger",
        r"godaddy.*parked",
        r"sedo\s*domain",
    ]

    # Wzorce wskazujące na placeholder/template
    PLACEHOLDER_PATTERNS = [
        r"lorem\s*ipsum",
        r"example\s*content",
        r"sample\s*text",
        r"your\s*company\s*name",
        r"twoja\s*firma",
        r"nazwa\s*firmy",
    ]

    def __init__(self, timeout: int = 10):
        """
        Inicjalizuje checker.

        Args:
            timeout: Timeout dla requestów w sekundach
        """
        self.timeout = timeout

    def check_website(self, url: str) -> WebsiteStatus:
        """
        Kompleksowo sprawdza stronę internetową.

        Args:
            url: URL do sprawdzenia

        Returns:
            WebsiteStatus z wynikami sprawdzenia
        """
        if not url:
            return WebsiteStatus(
                url="",
                exists=False,
                is_active=False,
                is_company_site=False,
                error="Empty URL"
            )

        # Normalizuj URL
        url = self._normalize_url(url)

        # Sprawdź podstawową walidację
        if not is_valid_website(url):
            return WebsiteStatus(
                url=url,
                exists=False,
                is_active=False,
                is_company_site=False,
                error="Not a company website (social media or directory)"
            )

        try:
            # Sprawdź DNS
            domain = urlparse(url).netloc
            try:
                socket.gethostbyname(domain)
            except socket.gaierror:
                return WebsiteStatus(
                    url=url,
                    exists=False,
                    is_active=False,
                    is_company_site=False,
                    error="DNS resolution failed"
                )

            # Wykonaj request
            response = requests.get(
                url,
                headers=get_headers(),
                timeout=self.timeout,
                allow_redirects=True,
                verify=False  # Niektóre strony mają nieważne certyfikaty
            )

            status_code = response.status_code
            final_url = response.url

            # Sprawdź status code
            if status_code >= 400:
                return WebsiteStatus(
                    url=url,
                    exists=False,
                    is_active=False,
                    is_company_site=False,
                    status_code=status_code,
                    error=f"HTTP error {status_code}"
                )

            # Sprawdź czy to parking domenowy
            is_parked = self._is_parking_page(response.text)
            if is_parked:
                return WebsiteStatus(
                    url=url,
                    exists=True,
                    is_active=False,
                    is_company_site=False,
                    status_code=status_code,
                    redirect_url=final_url if final_url != url else "",
                    error="Domain parking page detected"
                )

            # Sprawdź czy to placeholder
            is_placeholder = self._is_placeholder_page(response.text)
            if is_placeholder:
                return WebsiteStatus(
                    url=url,
                    exists=True,
                    is_active=False,
                    is_company_site=False,
                    status_code=status_code,
                    error="Placeholder/template page detected"
                )

            # Strona istnieje i wygląda na aktywną
            return WebsiteStatus(
                url=url,
                exists=True,
                is_active=True,
                is_company_site=True,
                status_code=status_code,
                redirect_url=final_url if final_url != url else ""
            )

        except requests.exceptions.Timeout:
            return WebsiteStatus(
                url=url,
                exists=False,
                is_active=False,
                is_company_site=False,
                error="Connection timeout"
            )
        except requests.exceptions.SSLError:
            # Próbuj bez SSL
            try:
                http_url = url.replace("https://", "http://")
                response = requests.get(
                    http_url,
                    headers=get_headers(),
                    timeout=self.timeout,
                    allow_redirects=True
                )
                return WebsiteStatus(
                    url=url,
                    exists=True,
                    is_active=response.status_code < 400,
                    is_company_site=not self._is_parking_page(response.text),
                    status_code=response.status_code,
                    error="SSL error, fallback to HTTP"
                )
            except Exception:
                return WebsiteStatus(
                    url=url,
                    exists=False,
                    is_active=False,
                    is_company_site=False,
                    error="SSL error"
                )
        except requests.exceptions.ConnectionError:
            return WebsiteStatus(
                url=url,
                exists=False,
                is_active=False,
                is_company_site=False,
                error="Connection failed"
            )
        except Exception as e:
            return WebsiteStatus(
                url=url,
                exists=False,
                is_active=False,
                is_company_site=False,
                error=str(e)
            )

    def _normalize_url(self, url: str) -> str:
        """Normalizuje URL dodając scheme jeśli brakuje."""
        url = url.strip()
        if not url:
            return ""

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        return url

    def _is_parking_page(self, html: str) -> bool:
        """Sprawdza czy strona to parking domenowy."""
        html_lower = html.lower()

        for pattern in self.PARKING_PATTERNS:
            if re.search(pattern, html_lower, re.IGNORECASE):
                return True

        # Sprawdź też krótką zawartość (parking pages są często minimalne)
        # Usuń tagi HTML i sprawdź długość tekstu
        text_only = re.sub(r'<[^>]+>', '', html)
        text_only = re.sub(r'\s+', ' ', text_only).strip()

        if len(text_only) < 100:
            return True

        return False

    def _is_placeholder_page(self, html: str) -> bool:
        """Sprawdza czy strona to placeholder/template."""
        html_lower = html.lower()

        for pattern in self.PLACEHOLDER_PATTERNS:
            if re.search(pattern, html_lower, re.IGNORECASE):
                return True

        return False

    def extract_contacts_from_website(self, url: str) -> Dict:
        """
        Wyciąga dane kontaktowe ze strony internetowej.

        Args:
            url: URL strony

        Returns:
            Dict z kontaktami (emails, phones, social)
        """
        result = {
            "emails": [],
            "phones": [],
            "social": {},
        }

        url = self._normalize_url(url)
        if not url:
            return result

        try:
            response = make_request(url, timeout=self.timeout)
            if not response:
                return result

            html = response.text

            # Wyciągnij emaile
            result["emails"] = extract_emails(html)

            # Wyciągnij telefony
            result["phones"] = extract_phones(html)

            # Wyciągnij social media
            result["social"] = extract_social_media(html)

            # Spróbuj też ze strony kontakt
            contact_urls = [
                f"{url.rstrip('/')}/kontakt",
                f"{url.rstrip('/')}/contact",
                f"{url.rstrip('/')}/kontakt.html",
                f"{url.rstrip('/')}/contact.html",
            ]

            for contact_url in contact_urls:
                try:
                    contact_response = make_request(contact_url, timeout=5)
                    if contact_response and contact_response.status_code == 200:
                        contact_html = contact_response.text

                        # Dodaj znalezione kontakty
                        for email in extract_emails(contact_html):
                            if email not in result["emails"]:
                                result["emails"].append(email)

                        for phone in extract_phones(contact_html):
                            if phone not in result["phones"]:
                                result["phones"].append(phone)

                        contact_social = extract_social_media(contact_html)
                        for platform, link in contact_social.items():
                            if link and not result["social"].get(platform):
                                result["social"][platform] = link

                        break  # Znaleziono stronę kontakt

                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting contacts from {url}: {e}")

        return result

    def batch_check(self, urls: list) -> list:
        """
        Sprawdza wiele URL-i naraz.

        Args:
            urls: Lista URL-i do sprawdzenia

        Returns:
            Lista WebsiteStatus
        """
        results = []
        for url in urls:
            status = self.check_website(url)
            results.append(status)
        return results


def has_no_website(business_data: dict) -> bool:
    """
    Uproszczona funkcja sprawdzająca czy firma nie ma strony.

    Args:
        business_data: Słownik z danymi firmy

    Returns:
        True jeśli firma NIE ma strony, False jeśli ma
    """
    website = business_data.get('website', '')

    if not website:
        return True

    checker = WebsiteChecker(timeout=5)
    status = checker.check_website(website)

    return not (status.exists and status.is_active and status.is_company_site)
