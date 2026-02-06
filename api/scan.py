"""
Vercel Serverless Function - Scan businesses from Polish directories
URL: /api/scan?industry=restauracje&max=20
"""
from http.server import BaseHTTPRequestHandler
import json
import re
import time
import random
from urllib.parse import urlparse, parse_qs, urljoin, quote

import requests
from bs4 import BeautifulSoup

# Spam data to filter out
SPAM_PHONES = {'224573095', '222992992', '801000500', '120951704', '223074002'}
SPAM_EMAILS = {'wenet.pl', 'panoramafirm.pl', 'pkt.pl'}
SPAM_NAMES = {'panorama firm', 'wenet', 'pkt.pl', 'dodaj firmę', 'reklama'}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }


def make_request(url, timeout=10):
    try:
        response = requests.get(url, headers=get_headers(), timeout=timeout, allow_redirects=True)
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
    email_lower = email.lower()
    return any(spam in email_lower for spam in SPAM_EMAILS)


def is_spam_name(name):
    if not name:
        return True
    name_lower = name.lower()
    return any(spam in name_lower for spam in SPAM_NAMES) or len(name) < 3


def extract_phones(text):
    if not text:
        return []
    patterns = [
        r'\+48\s*\d{3}\s*\d{3}\s*\d{3}',
        r'(?<!\d)\d{3}[-.\s]?\d{3}[-.\s]?\d{3}(?!\d)',
        r'(?<!\d)\d{2}[-.\s]?\d{3}[-.\s]?\d{2}[-.\s]?\d{2}(?!\d)'
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

    fb_matches = re.findall(r'href=["\']?(https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+))["\']?', html, re.I)
    for url, name in fb_matches:
        if name.lower() not in ['panoramafirm', 'wenet', 'sharer', 'share', 'pages', 'profile.php', 'tr']:
            social["facebook"] = f"https://facebook.com/{name}"
            break

    ig_matches = re.findall(r'href=["\']?(https?://(?:www\.)?instagram\.com/([a-zA-Z0-9._-]+))["\']?', html, re.I)
    for url, name in ig_matches:
        if name.lower() not in ['panoramafirm', 'p', 'explore', 'accounts']:
            social["instagram"] = f"https://instagram.com/{name}"
            break

    return social


def clean_text(text):
    if not text:
        return ""
    return ' '.join(text.split()).strip()


def scrape_panoramafirm(industry, city="szczecin", max_results=20):
    """Scrape businesses from Panorama Firm with pagination."""
    businesses = []
    base_url = "https://panoramafirm.pl"
    seen_names = set()

    # Try multiple pages to get diverse results
    pages_to_try = list(range(1, 8))
    random.shuffle(pages_to_try)

    for page in pages_to_try[:4]:  # Try 4 random pages
        if len(businesses) >= max_results:
            break

        if page == 1:
            url = f"{base_url}/{quote(industry)}/{city.lower()}"
        else:
            url = f"{base_url}/{quote(industry)}/{city.lower()}/firmy,{page}"

        response = make_request(url)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "lxml")

        # Find company links - multiple selectors for different page layouts
        links = soup.select("a.company-name, a.ajax-company-loading, h2 a[href*='.html'], a.addax-cs_hl_hit_company_name_click")

        if not links:
            # Alternative: find within company containers
            containers = soup.select("li.company-item, div.company-item, article, div[data-company-id]")
            for container in containers:
                link = container.select_one("a[href*='.html']")
                if link and link not in links:
                    links.append(link)

        for link in links:
            if len(businesses) >= max_results:
                break

            name = clean_text(link.get_text())
            if is_spam_name(name) or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            detail_url = link.get("href", "")
            if detail_url and not detail_url.startswith("http"):
                detail_url = urljoin(base_url, detail_url)

            if '/szukaj' in detail_url or '/kategorie' in detail_url:
                continue

            biz = {
                "name": name,
                "industry": industry,
                "address": "",
                "phone": "",
                "email": "",
                "website": "",
                "facebook": "",
                "instagram": "",
                "has_website": False,
                "source": "panoramafirm"
            }

            # Visit detail page for contact info
            if detail_url:
                time.sleep(random.uniform(0.2, 0.5))
                detail_resp = make_request(detail_url, timeout=8)

                if detail_resp:
                    dsoup = BeautifulSoup(detail_resp.text, "lxml")
                    detail_html = detail_resp.text

                    # Find main content area (avoid header/footer spam)
                    main = dsoup.select_one("main, #company-details, .company-details, article")
                    if not main:
                        main = dsoup

                    main_text = main.get_text() if main else ""

                    # Phone - try specific selectors first
                    phone_elem = main.select_one("a[href^='tel:'], [itemprop='telephone']")
                    if phone_elem:
                        phone_text = phone_elem.get("href", "").replace("tel:", "") or phone_elem.get_text()
                        phones = extract_phones(phone_text)
                        if phones:
                            biz["phone"] = phones[0]

                    # If no phone from selector, try from main content
                    if not biz["phone"]:
                        phones = extract_phones(main_text)
                        if phones:
                            biz["phone"] = phones[0]

                    # Email
                    email_elem = main.select_one("a[href^='mailto:']")
                    if email_elem:
                        email = email_elem.get("href", "").replace("mailto:", "").split("?")[0]
                        if not is_spam_email(email):
                            biz["email"] = email

                    if not biz["email"]:
                        emails = extract_emails(main_text)
                        if emails:
                            biz["email"] = emails[0]

                    # Address
                    addr_elem = main.select_one("[itemprop='streetAddress'], .street-address, .address")
                    if addr_elem:
                        biz["address"] = clean_text(addr_elem.get_text())[:100]

                    # Website
                    www_elem = main.select_one("a[data-stat-id='www'], a.company-www, a[rel='nofollow'][target='_blank']")
                    if www_elem:
                        website = www_elem.get("href", "")
                        if website and "panoramafirm" not in website.lower() and "pkt.pl" not in website.lower():
                            biz["website"] = website
                            biz["has_website"] = True

                    # Social media
                    social = extract_social(detail_html)
                    biz["facebook"] = social["facebook"]
                    biz["instagram"] = social["instagram"]

            # Only add if we have at least some contact info
            if name and (biz["phone"] or biz["email"] or biz["facebook"]):
                businesses.append(biz)

    return businesses


def scrape_businesses(industry, city="szczecin", max_results=20):
    """Scrape from Polish business directories."""
    all_businesses = []
    seen_phones = set()
    seen_names = set()

    # Get from Panorama Firm
    pf_results = scrape_panoramafirm(industry, city, max_results + 5)

    # Deduplicate
    for biz in pf_results:
        if len(all_businesses) >= max_results:
            break

        # Skip if same phone already seen
        if biz["phone"] and biz["phone"] in seen_phones:
            continue

        # Skip if same name already seen
        name_key = biz["name"].lower()[:20]
        if name_key in seen_names:
            continue

        if biz["phone"]:
            seen_phones.add(biz["phone"])
        seen_names.add(name_key)

        all_businesses.append(biz)

    # Shuffle results for variety
    random.shuffle(all_businesses)

    return all_businesses[:max_results]


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
