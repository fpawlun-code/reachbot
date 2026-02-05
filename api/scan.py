"""
Vercel Serverless Function - Scan businesses via Google Search
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

# Spam data to filter out
SPAM_PHONES = {'224573095', '222992992', '801000500', '120951704'}
SPAM_EMAILS = {'wenet.pl', 'panoramafirm.pl', 'pkt.pl'}
SPAM_DOMAINS = ['panoramafirm.pl', 'pkt.pl', 'wenet.pl', 'yelp.com', 'tripadvisor',
                'zomato.com', 'google.com', 'facebook.com', 'instagram.com']

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def make_request(url, timeout=10):
    try:
        response = requests.get(url, headers=get_headers(), timeout=timeout)
        response.raise_for_status()
        return response
    except Exception:
        return None


def is_spam_phone(phone):
    normalized = re.sub(r'\D', '', phone)[-9:]
    return normalized in SPAM_PHONES or len(normalized) < 9


def is_spam_email(email):
    return any(spam in email.lower() for spam in SPAM_EMAILS)


def is_spam_domain(url):
    if not url:
        return True
    url_lower = url.lower()
    return any(spam in url_lower for spam in SPAM_DOMAINS)


def extract_phones(text):
    patterns = [
        r'\+48\s*\d{3}\s*\d{3}\s*\d{3}',
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{3}',
        r'\(\d{2}\)\s*\d{3}[-.\s]?\d{2}[-.\s]?\d{2}'
    ]
    phones = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            normalized = re.sub(r'\D', '', match)[-9:]
            if normalized and not is_spam_phone(normalized) and normalized not in phones:
                phones.append(normalized)
    return phones


def extract_emails(text):
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = []
    for email in re.findall(pattern, text.lower()):
        if not is_spam_email(email) and email not in emails:
            emails.append(email)
    return emails[:3]


def extract_social(html):
    social = {"facebook": "", "instagram": ""}

    fb_matches = re.findall(r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)/?', html, re.I)
    for match in fb_matches:
        if match.lower() not in ['panoramafirm', 'wenet', 'sharer', 'share', 'pages', 'profile.php']:
            social["facebook"] = f"https://facebook.com/{match}"
            break

    ig = re.search(r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._-]+)/?', html, re.I)
    if ig and ig.group(1).lower() not in ['panoramafirm', 'p', 'explore']:
        social["instagram"] = f"https://instagram.com/{ig.group(1)}"

    return social


def clean_text(text):
    return ' '.join(text.split()).strip() if text else ''


def search_google(query, num_results=20):
    """Search Google and return business URLs."""
    results = []

    # Google search URL
    search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={num_results + 10}&hl=pl"

    response = make_request(search_url)
    if not response:
        return results

    soup = BeautifulSoup(response.text, "lxml")

    # Find all search result links
    for result in soup.select("div.g"):
        link = result.select_one("a[href^='http']")
        if not link:
            continue

        url = link.get("href", "")

        # Skip spam/aggregator domains
        if is_spam_domain(url):
            continue

        # Get title
        title_elem = result.select_one("h3")
        title = clean_text(title_elem.get_text()) if title_elem else ""

        # Get snippet for address hints
        snippet_elem = result.select_one("div.VwiC3b, span.aCOpRe")
        snippet = clean_text(snippet_elem.get_text()) if snippet_elem else ""

        if url and title:
            results.append({
                "url": url,
                "title": title,
                "snippet": snippet
            })

        if len(results) >= num_results:
            break

    return results


def search_duckduckgo(query, num_results=20):
    """Search DuckDuckGo as fallback."""
    results = []

    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    response = make_request(search_url)
    if not response:
        return results

    soup = BeautifulSoup(response.text, "lxml")

    for result in soup.select("div.result"):
        link = result.select_one("a.result__a")
        if not link:
            continue

        url = link.get("href", "")
        title = clean_text(link.get_text())

        # DuckDuckGo uses redirect URLs, extract actual URL
        if "uddg=" in url:
            from urllib.parse import unquote
            match = re.search(r'uddg=([^&]+)', url)
            if match:
                url = unquote(match.group(1))

        if is_spam_domain(url):
            continue

        snippet_elem = result.select_one("a.result__snippet")
        snippet = clean_text(snippet_elem.get_text()) if snippet_elem else ""

        if url and title:
            results.append({
                "url": url,
                "title": title,
                "snippet": snippet
            })

        if len(results) >= num_results:
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

    # Try to extract address from snippet
    addr_match = re.search(r'(ul\.|ulica|al\.|aleja)[\s.]+[^,]+,?\s*\d{2}-\d{3}\s*\w+', snippet, re.I)
    if addr_match:
        biz["address"] = addr_match.group(0)
    elif "Szczecin" in snippet:
        # Try to find address pattern near Szczecin
        addr_match = re.search(r'[^,]+,?\s*\d{2}-\d{3}\s*Szczecin', snippet, re.I)
        if addr_match:
            biz["address"] = addr_match.group(0)

    # Extract phone from snippet
    phones = extract_phones(snippet)
    if phones:
        biz["phone"] = phones[0]

    # Now visit the actual website
    time.sleep(random.uniform(0.3, 0.8))
    response = make_request(url, timeout=8)

    if response:
        try:
            html = response.text
            soup = BeautifulSoup(html, "lxml")

            # Remove script and style tags
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

            # Address - look for structured data
            addr_elem = soup.select_one(
                "[itemprop='streetAddress'], [itemprop='address'], "
                ".address, .contact-address, .location"
            )
            if addr_elem and not biz["address"]:
                biz["address"] = clean_text(addr_elem.get_text())[:100]

            # Social media
            social = extract_social(html)
            biz["facebook"] = social.get("facebook", "")
            biz["instagram"] = social.get("instagram", "")

        except Exception:
            pass

    return biz


def scrape_businesses(industry, city="szczecin", max_results=20):
    """Search for businesses and scrape their info."""
    businesses = []
    seen_domains = set()

    # Build search query
    query = f"{industry} {city}"

    # Try Google first, then DuckDuckGo
    search_results = search_google(query, max_results + 10)

    if len(search_results) < 5:
        # Fallback to DuckDuckGo
        search_results = search_duckduckgo(query, max_results + 10)

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

        # Clean up title (remove " - strona główna" etc)
        biz["name"] = re.sub(r'\s*[-–|]\s*(strona główna|home|oficjalna|kontakt).*$', '', biz["name"], flags=re.I)
        biz["name"] = biz["name"][:80]  # Limit length

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
