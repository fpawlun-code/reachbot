"""
Vercel Serverless Function - Scan businesses via Google Custom Search API
URL: /api/scan?industry=restauracje&max=20
"""
from http.server import BaseHTTPRequestHandler
import json
import re
import time
import random
from urllib.parse import urlparse, parse_qs, urljoin, quote_plus

import requests
from bs4 import BeautifulSoup

# Google Custom Search API credentials
GOOGLE_API_KEY = "AIzaSyCIx_sO4dZZiRKZ2OcKpYPu-GAzh00H9ws"
GOOGLE_SEARCH_ENGINE_ID = "25ec1a1bc8e2b44e7"

# Spam data to filter out
SPAM_PHONES = {'224573095', '222992992', '801000500', '120951704', '223074002'}
SPAM_EMAILS = {'wenet.pl', 'panoramafirm.pl', 'pkt.pl'}
SPAM_DOMAINS = ['panoramafirm.pl', 'pkt.pl', 'wenet.pl', 'yelp.com', 'tripadvisor',
                'zomato.com', 'google.com', 'facebook.com', 'instagram.com', 'youtube.com']

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }


def make_request(url, timeout=10):
    try:
        response = requests.get(url, headers=get_headers(), timeout=timeout)
        response.raise_for_status()
        return response
    except Exception:
        return None


def is_spam_phone(phone):
    if not phone:
        return True
    normalized = re.sub(r'\D', '', str(phone))[-9:]
    return normalized in SPAM_PHONES or len(normalized) < 9


def is_spam_email(email):
    if not email:
        return True
    return any(spam in email.lower() for spam in SPAM_EMAILS)


def is_spam_domain(url):
    if not url:
        return True
    return any(spam in url.lower() for spam in SPAM_DOMAINS)


def extract_phones(text):
    if not text:
        return []
    patterns = [
        r'\+48\s*\d{3}\s*\d{3}\s*\d{3}',
        r'(?<!\d)\d{3}[-.\s]?\d{3}[-.\s]?\d{3}(?!\d)',
    ]
    phones = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            normalized = re.sub(r'\D', '', match)[-9:]
            if normalized and not is_spam_phone(normalized) and normalized not in phones:
                phones.append(normalized)
    return phones


def extract_emails(text):
    if not text:
        return []
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = []
    for email in re.findall(pattern, text.lower()):
        if not is_spam_email(email) and email not in emails:
            emails.append(email)
    return emails[:3]


def extract_social(html):
    social = {"facebook": "", "instagram": ""}
    if not html:
        return social

    fb = re.search(r'facebook\.com/([a-zA-Z0-9._-]+)', html, re.I)
    if fb and fb.group(1).lower() not in ['sharer', 'share', 'pages', 'tr']:
        social["facebook"] = f"https://facebook.com/{fb.group(1)}"

    ig = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', html, re.I)
    if ig and ig.group(1).lower() not in ['p', 'explore']:
        social["instagram"] = f"https://instagram.com/{ig.group(1)}"

    return social


def clean_text(text):
    return ' '.join(text.split()).strip() if text else ""


def google_search(query, num_results=10):
    """Search using Google Custom Search API."""
    results = []

    # Google Custom Search API - max 10 results per request
    start_index = 1

    while len(results) < num_results:
        url = (
            f"https://www.googleapis.com/customsearch/v1"
            f"?key={GOOGLE_API_KEY}"
            f"&cx={GOOGLE_SEARCH_ENGINE_ID}"
            f"&q={quote_plus(query)}"
            f"&num=10"
            f"&start={start_index}"
            f"&lr=lang_pl"
            f"&gl=pl"
        )

        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if "items" not in data:
                break

            for item in data["items"]:
                link = item.get("link", "")

                # Skip spam domains
                if is_spam_domain(link):
                    continue

                results.append({
                    "url": link,
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", "")
                })

                if len(results) >= num_results:
                    break

            start_index += 10

            # Google API limit - max 100 results total
            if start_index > 91:
                break

        except Exception as e:
            break

    return results


def scrape_business_page(url, title, snippet, industry):
    """Scrape contact info from a business website."""
    biz = {
        "name": title,
        "industry": industry,
        "address": "",
        "phone": "",
        "email": "",
        "website": url,
        "facebook": "",
        "instagram": "",
        "has_website": True,
    }

    # Clean up title
    biz["name"] = re.sub(r'\s*[-–|]\s*(strona główna|home|oficjalna|kontakt).*$', '', title, flags=re.I)
    biz["name"] = biz["name"][:80]

    # Extract from snippet first
    phones = extract_phones(snippet)
    if phones:
        biz["phone"] = phones[0]

    # Address pattern in snippet
    addr_match = re.search(r'(ul\.|ulica|al\.)[\s.]+[^,]+,?\s*\d{2}-\d{3}', snippet, re.I)
    if addr_match:
        biz["address"] = addr_match.group(0)
    elif "Szczecin" in snippet:
        addr_match = re.search(r'[^,]+\d{2}-\d{3}\s*Szczecin', snippet, re.I)
        if addr_match:
            biz["address"] = addr_match.group(0)

    # Visit actual website for more data
    time.sleep(random.uniform(0.2, 0.5))
    response = make_request(url, timeout=8)

    if response:
        try:
            html = response.text
            soup = BeautifulSoup(html, "lxml")

            # Remove scripts/styles
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            text = soup.get_text()

            # Phone
            if not biz["phone"]:
                phones = extract_phones(text)
                if phones:
                    biz["phone"] = phones[0]

            # Email
            emails = extract_emails(text)
            if emails:
                biz["email"] = emails[0]

            # Address from structured data
            if not biz["address"]:
                addr_elem = soup.select_one("[itemprop='streetAddress'], .address, .contact-address")
                if addr_elem:
                    biz["address"] = clean_text(addr_elem.get_text())[:100]

            # Social media
            social = extract_social(html)
            biz["facebook"] = social["facebook"]
            biz["instagram"] = social["instagram"]

        except Exception:
            pass

    return biz


def scrape_businesses(industry, city="szczecin", max_results=20):
    """Search for businesses using Google and scrape their info."""
    businesses = []
    seen_domains = set()

    # Build search query
    query = f"{industry} {city}"

    # Get results from Google Custom Search API
    search_results = google_search(query, max_results + 10)

    for result in search_results:
        if len(businesses) >= max_results:
            break

        url = result["url"]

        # Extract domain to avoid duplicates
        try:
            domain = urlparse(url).netloc.replace("www.", "")
        except:
            continue

        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        # Scrape the business page
        biz = scrape_business_page(
            url=result["url"],
            title=result["title"],
            snippet=result["snippet"],
            industry=industry
        )

        businesses.append(biz)

    return businesses


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        industry = params.get('industry', ['restauracje'])[0]
        max_results = min(int(params.get('max', ['20'])[0]), 30)

        try:
            businesses = scrape_businesses(industry, "szczecin", max_results)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            response = {
                "industry": industry,
                "count": len(businesses),
                "businesses": businesses
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
