"""
Vercel Serverless Function - Business Scanner API
"""
import json
import re
import time
import random
from urllib.parse import urljoin, quote
from http.server import BaseHTTPRequestHandler

import requests
from bs4 import BeautifulSoup


# Simple request helper
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


def extract_phones(text):
    """Extract phone numbers from text."""
    patterns = [
        r'\+48\s*\d{3}\s*\d{3}\s*\d{3}',
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{3}',
    ]
    phones = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            normalized = re.sub(r'\D', '', match)
            if len(normalized) >= 9:
                phones.add(normalized[-9:])
    return list(phones)


def extract_emails(text):
    """Extract emails from text."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text.lower())
    return list(set(emails))[:3]


def extract_social(text):
    """Extract social media links."""
    social = {"facebook": None, "instagram": None}

    fb_match = re.search(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+/?', text, re.I)
    if fb_match:
        url = fb_match.group(0)
        if not url.startswith('http'):
            url = 'https://' + url
        social["facebook"] = url

    ig_match = re.search(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+/?', text, re.I)
    if ig_match:
        url = ig_match.group(0)
        if not url.startswith('http'):
            url = 'https://' + url
        social["instagram"] = url

    return social


def is_valid_website(url):
    """Check if URL is a real company website."""
    if not url:
        return False
    excluded = ['facebook.com', 'instagram.com', 'google.', 'panoramafirm.pl', 'pkt.pl']
    return not any(ex in url.lower() for ex in excluded)


def clean_text(text):
    """Clean whitespace from text."""
    return ' '.join(text.split()).strip() if text else ''


def scrape_panorama_firm(industry, city="szczecin", max_results=5):
    """Scrape businesses from Panorama Firm."""
    businesses = []
    base_url = "https://panoramafirm.pl"
    category_url = f"{base_url}/{quote(industry)}/{city.lower()}"

    response = make_request(category_url)
    if not response:
        return businesses

    soup = BeautifulSoup(response.text, "lxml")

    # Find company links
    links = soup.select("a.addax-cs_hl_hit_company_name_click")
    if not links:
        links = soup.select("a[href*='/firma/'], a[href*='panoramafirm.pl'][href*='.html']")

    seen = set()
    for link in links[:max_results * 2]:  # Get more to filter
        if len(businesses) >= max_results:
            break

        href = link.get("href", "")
        name = clean_text(link.get_text())

        if not name or not href or name in seen:
            continue
        seen.add(name)

        if not href.startswith("http"):
            href = urljoin(base_url, href)

        # Fetch details
        time.sleep(random.uniform(0.5, 1))
        detail_resp = make_request(href, timeout=8)

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
            "source": "panorama_firm"
        }

        if detail_resp:
            detail_soup = BeautifulSoup(detail_resp.text, "lxml")
            html = detail_resp.text

            # Address
            addr_elem = detail_soup.select_one("[itemprop='address'], .address, address")
            if addr_elem:
                biz["address"] = clean_text(addr_elem.get_text())

            # Phone
            phone_elem = detail_soup.select_one("a[href^='tel:']")
            if phone_elem:
                biz["phone"] = phone_elem.get("href", "").replace("tel:", "")
            if not biz["phone"]:
                phones = extract_phones(html)
                if phones:
                    biz["phone"] = phones[0]

            # Email
            email_elem = detail_soup.select_one("a[href^='mailto:']")
            if email_elem:
                biz["email"] = email_elem.get("href", "").replace("mailto:", "")
            if not biz["email"]:
                emails = extract_emails(html)
                if emails:
                    biz["email"] = emails[0]

            # Website
            www_elem = detail_soup.select_one("a[data-stat-id='www'], a.website")
            if www_elem:
                href = www_elem.get("href", "")
                if is_valid_website(href):
                    biz["website"] = href
                    biz["has_website"] = True

            # Social
            social = extract_social(html)
            biz["facebook"] = social.get("facebook", "")
            biz["instagram"] = social.get("instagram", "")

        businesses.append(biz)

    return businesses


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query params
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        industry = params.get('industry', ['restauracje'])[0]
        max_results = int(params.get('max', ['5'])[0])
        max_results = min(max_results, 10)  # Limit to 10

        try:
            businesses = scrape_panorama_firm(industry, "szczecin", max_results)

            response = {
                "industry": industry,
                "count": len(businesses),
                "businesses": businesses
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
