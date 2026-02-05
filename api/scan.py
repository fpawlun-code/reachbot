"""
Vercel Serverless Function - Scan businesses
URL: /api/scan?industry=restauracje&max=5
"""
from http.server import BaseHTTPRequestHandler
import json
import re
import time
import random
from urllib.parse import urlparse, parse_qs, urljoin, quote

import requests
from bs4 import BeautifulSoup

# Spam data to filter out (Panorama Firm / WeNet contact info)
SPAM_PHONES = {'224573095', '222992992', '801000500'}
SPAM_EMAILS = {'wenet.pl', 'panoramafirm.pl', 'pkt.pl'}


def make_request(url, timeout=10):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except Exception:
        return None


def is_spam_phone(phone):
    """Check if phone is spam."""
    normalized = re.sub(r'\D', '', phone)[-9:]
    return normalized in SPAM_PHONES


def is_spam_email(email):
    """Check if email is spam."""
    return any(spam in email.lower() for spam in SPAM_EMAILS)


def extract_phones(text):
    """Extract phone numbers, filtering spam."""
    patterns = [r'\+48\s*\d{3}\s*\d{3}\s*\d{3}', r'\d{3}[-.\s]?\d{3}[-.\s]?\d{3}']
    phones = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            normalized = re.sub(r'\D', '', match)[-9:]
            if normalized and not is_spam_phone(normalized) and normalized not in phones:
                phones.append(normalized)
    return phones


def extract_emails(text):
    """Extract emails, filtering spam."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = []
    for email in re.findall(pattern, text.lower()):
        if not is_spam_email(email) and email not in emails:
            emails.append(email)
    return emails[:3]


def extract_social(html):
    """Extract social media from company section only."""
    social = {"facebook": "", "instagram": ""}

    # Look for Facebook - but exclude Panorama Firm's FB
    fb_matches = re.findall(r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9._-]+)/?', html, re.I)
    for match in fb_matches:
        if match.lower() not in ['panoramafirm', 'wenet', 'sharer', 'share']:
            social["facebook"] = f"https://facebook.com/{match}"
            break

    # Instagram
    ig = re.search(r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._-]+)/?', html, re.I)
    if ig and ig.group(1).lower() not in ['panoramafirm']:
        social["instagram"] = f"https://instagram.com/{ig.group(1)}"

    return social


def is_valid_website(url):
    if not url:
        return False
    excluded = ['facebook.com', 'instagram.com', 'google.', 'panoramafirm.pl', 'pkt.pl', 'wenet.pl']
    return not any(ex in url.lower() for ex in excluded)


def clean_text(text):
    return ' '.join(text.split()).strip() if text else ''


def scrape_businesses(industry, city="szczecin", max_results=5):
    """Scrape businesses from Panorama Firm."""
    businesses = []
    base_url = "https://panoramafirm.pl"
    category_url = f"{base_url}/{quote(industry)}/{city.lower()}"

    response = make_request(category_url)
    if not response:
        return businesses

    soup = BeautifulSoup(response.text, "lxml")

    # Find company links - be more specific
    links = soup.select("a.addax-cs_hl_hit_company_name_click")
    if not links:
        # Try finding links within company cards/articles
        cards = soup.select("article, div.company-item, div[data-id]")
        links = []
        for card in cards:
            link = card.select_one("a[href*='.html']")
            if link:
                links.append(link)

    seen = set()
    for link in links[:max_results * 2]:
        if len(businesses) >= max_results:
            break

        href = link.get("href", "")
        name = clean_text(link.get_text())

        if not name or not href or name in seen or len(name) < 3:
            continue
        seen.add(name)

        if not href.startswith("http"):
            href = urljoin(base_url, href)

        # Skip non-company pages
        if '/szukaj' in href or '/kategorie' in href:
            continue

        time.sleep(random.uniform(0.5, 1.0))
        detail = make_request(href, timeout=8)

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
        }

        if detail:
            dsoup = BeautifulSoup(detail.text, "lxml")

            # Find the main company content area (exclude header/footer)
            main_content = dsoup.select_one("main, .company-details, article, #content")
            if not main_content:
                main_content = dsoup

            html = str(main_content)

            # Address - look for structured data first
            addr = main_content.select_one(
                "[itemprop='streetAddress'], [itemprop='address'], "
                ".street-address, .company-address, .address-line"
            )
            if addr:
                biz["address"] = clean_text(addr.get_text())
            else:
                # Try to find address pattern
                addr_container = main_content.select_one(".address, address")
                if addr_container:
                    biz["address"] = clean_text(addr_container.get_text())

            # Phone - look in specific company contact section
            phone_elem = main_content.select_one(
                "[itemprop='telephone'], "
                ".company-phone a[href^='tel:'], "
                ".phone-number a[href^='tel:'], "
                "a.phone[href^='tel:']"
            )
            if phone_elem:
                phone_val = phone_elem.get("href", "").replace("tel:", "")
                if not phone_val:
                    phone_val = clean_text(phone_elem.get_text())
                if phone_val and not is_spam_phone(phone_val):
                    biz["phone"] = re.sub(r'\D', '', phone_val)[-9:]

            # If no phone from element, try regex but only from company section
            if not biz["phone"]:
                phones = extract_phones(html)
                if phones:
                    biz["phone"] = phones[0]

            # Email - look in company contact section
            email_elem = main_content.select_one(
                "[itemprop='email'], "
                ".company-email a[href^='mailto:'], "
                "a.email[href^='mailto:']"
            )
            if email_elem:
                email_val = email_elem.get("href", "").replace("mailto:", "")
                if email_val and not is_spam_email(email_val):
                    biz["email"] = email_val

            if not biz["email"]:
                emails = extract_emails(html)
                if emails:
                    biz["email"] = emails[0]

            # Website
            www_elem = main_content.select_one(
                "a[data-stat-id='www'], "
                "a.company-www, "
                "a.website-link"
            )
            if www_elem:
                href_val = www_elem.get("href", "")
                if is_valid_website(href_val):
                    biz["website"] = href_val
                    biz["has_website"] = True

            # Social media
            social = extract_social(html)
            biz["facebook"] = social.get("facebook", "")
            biz["instagram"] = social.get("instagram", "")

        businesses.append(biz)

    return businesses


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        industry = params.get('industry', ['restauracje'])[0]
        max_results = min(int(params.get('max', ['5'])[0]), 10)

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
