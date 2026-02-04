"""
Funkcje pomocnicze dla scrapera
"""
import random
import time
import logging
from typing import Optional, Dict, Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from config import (
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    USER_AGENTS,
    USE_PROXY,
    PROXY_URL,
)

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def random_delay(min_delay: float = None, max_delay: float = None) -> None:
    """
    Dodaje losowe opóźnienie między requestami.
    Kluczowe dla uniknięcia blokad i rate limitów.
    """
    min_d = min_delay or REQUEST_DELAY_MIN
    max_d = max_delay or REQUEST_DELAY_MAX
    delay = random.uniform(min_d, max_d)
    logger.debug(f"Czekam {delay:.2f}s...")
    time.sleep(delay)


def get_random_user_agent() -> str:
    """Zwraca losowy User-Agent dla symulacji różnych przeglądarek."""
    return random.choice(USER_AGENTS)


def get_headers() -> Dict[str, str]:
    """Generuje nagłówki HTTP imitujące prawdziwą przeglądarkę."""
    return {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


def get_proxies() -> Optional[Dict[str, str]]:
    """Zwraca konfigurację proxy jeśli jest włączona."""
    if USE_PROXY and PROXY_URL:
        return {
            "http": PROXY_URL,
            "https": PROXY_URL,
        }
    return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def make_request(
    url: str,
    method: str = "GET",
    params: Dict = None,
    data: Dict = None,
    json_data: Dict = None,
    timeout: int = 30,
    allow_redirects: bool = True,
) -> Optional[requests.Response]:
    """
    Wykonuje request HTTP z obsługą retry i rate limiting.

    Args:
        url: URL do pobrania
        method: Metoda HTTP (GET, POST)
        params: Parametry URL
        data: Dane formularza
        json_data: Dane JSON
        timeout: Timeout w sekundach
        allow_redirects: Czy podążać za przekierowaniami

    Returns:
        Response object lub None w przypadku błędu
    """
    try:
        headers = get_headers()
        proxies = get_proxies()

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            json=json_data,
            timeout=timeout,
            proxies=proxies,
            allow_redirects=allow_redirects,
        )

        # Sprawdź status
        if response.status_code == 429:
            logger.warning(f"Rate limit hit for {url}. Waiting longer...")
            time.sleep(30)  # Dłuższa przerwa przy rate limit
            raise requests.exceptions.RequestException("Rate limited")

        if response.status_code == 403:
            logger.warning(f"Access forbidden for {url}. Might be blocked.")
            return None

        response.raise_for_status()
        return response

    except requests.exceptions.Timeout:
        logger.error(f"Timeout for {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        raise


def clean_text(text: str) -> str:
    """Czyści tekst z nadmiarowych białych znaków."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def normalize_phone(phone: str) -> str:
    """Normalizuje numer telefonu do standardowego formatu."""
    if not phone:
        return ""
    # Usuń wszystko poza cyframi i +
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    # Dodaj prefix +48 jeśli brakuje
    if cleaned and not cleaned.startswith("+"):
        if cleaned.startswith("48") and len(cleaned) == 11:
            cleaned = "+" + cleaned
        elif len(cleaned) == 9:
            cleaned = "+48" + cleaned
    return cleaned
