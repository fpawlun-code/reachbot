"""
Walidatory i ekstraktory danych kontaktowych
"""
import re
from typing import List, Set
from urllib.parse import urlparse


def is_valid_email(email: str) -> bool:
    """Sprawdza czy email jest poprawny."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.lower()))


def is_valid_phone(phone: str) -> bool:
    """Sprawdza czy numer telefonu jest poprawny (polski format)."""
    if not phone:
        return False
    # Usuń wszystko poza cyframi
    digits = re.sub(r'\D', '', phone)
    # Polski numer: 9 cyfr lub 11 z kodem kraju
    return len(digits) in [9, 11, 12]


def extract_emails(text: str) -> List[str]:
    """Wyciąga wszystkie adresy email z tekstu."""
    if not text:
        return []
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text.lower())
    # Filtruj i usuń duplikaty
    valid_emails = []
    seen = set()
    for email in emails:
        if email not in seen and is_valid_email(email):
            # Wyklucz popularne fałszywe emaile
            if not any(fake in email for fake in ['example.com', 'test.com', 'email@', '@email']):
                valid_emails.append(email)
                seen.add(email)
    return valid_emails


def extract_phones(text: str) -> List[str]:
    """Wyciąga wszystkie numery telefonów z tekstu."""
    if not text:
        return []

    # Wzorce dla polskich numerów telefonów
    patterns = [
        r'\+48\s*\d{3}\s*\d{3}\s*\d{3}',  # +48 123 456 789
        r'\+48\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}',  # +48 12 345 67 89
        r'\(\+48\)\s*\d{3}\s*\d{3}\s*\d{3}',  # (+48) 123 456 789
        r'48\s*\d{3}\s*\d{3}\s*\d{3}',  # 48 123 456 789
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{3}',  # 123-456-789, 123.456.789, 123 456 789
        r'\d{2}[-.\s]?\d{3}[-.\s]?\d{2}[-.\s]?\d{2}',  # 12-345-67-89
        r'\d{9}',  # 123456789
    ]

    phones = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Normalizuj
            normalized = re.sub(r'\D', '', match)
            if len(normalized) >= 9:
                # Weź ostatnie 9 cyfr (właściwy numer bez kodu kraju)
                if len(normalized) > 9:
                    normalized = normalized[-9:]
                phones.add(normalized)

    return list(phones)


def extract_social_media(text: str, html: str = None) -> dict:
    """
    Wyciąga linki do social media z tekstu/HTML.

    Returns:
        Dict z kluczami: facebook, instagram, linkedin, twitter
    """
    social = {
        "facebook": None,
        "instagram": None,
        "linkedin": None,
        "twitter": None,
    }

    source = f"{text} {html}" if html else text
    if not source:
        return social

    # Wzorce dla różnych platform
    patterns = {
        "facebook": [
            r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+/?',
            r'(?:https?://)?(?:www\.)?fb\.com/[a-zA-Z0-9._-]+/?',
        ],
        "instagram": [
            r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+/?',
        ],
        "linkedin": [
            r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+/?',
        ],
        "twitter": [
            r'(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9._-]+/?',
        ],
    }

    for platform, platform_patterns in patterns.items():
        for pattern in platform_patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                url = match.group(0)
                # Dodaj https:// jeśli brakuje
                if not url.startswith('http'):
                    url = 'https://' + url
                social[platform] = url
                break

    return social


def is_valid_website(url: str) -> bool:
    """
    Sprawdza czy URL wygląda na prawdziwą stronę firmową.
    Wyklucza social media, katalogi firm, itp.
    """
    if not url:
        return False

    # Parsuj URL
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc or parsed.path.split('/')[0]
    except Exception:
        return False

    # Domeny, które NIE są stronami firmowymi
    excluded_domains = [
        'facebook.com', 'fb.com',
        'instagram.com',
        'twitter.com', 'x.com',
        'linkedin.com',
        'youtube.com',
        'tiktok.com',
        'google.com', 'google.pl',
        'panoramafirm.pl',
        'pkt.pl',
        'aleo.com',
        'gowork.pl',
        'olx.pl',
        'allegro.pl',
        'zumi.pl',
        'yelp.com',
        'tripadvisor.',
        'booking.com',
    ]

    return not any(excluded in domain for excluded in excluded_domains)


def has_website(business_data: dict) -> bool:
    """
    Sprawdza czy firma ma własną stronę internetową.

    Args:
        business_data: Słownik z danymi firmy

    Returns:
        True jeśli firma ma stronę, False jeśli nie
    """
    website = business_data.get('website', '')

    if not website:
        return False

    return is_valid_website(website)
