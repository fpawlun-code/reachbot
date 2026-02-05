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


def make_request(url, timeout=10):
    """Make HTTP request with headers."""
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
    """Extract phone numbers."""
    patterns = [r'\+48\s*\d{3}\s*\d{3}\s*\d{3}', r'\d{3}[-.\s]?\d{3}[-.\s]?\d{3}']
    phones = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            normalized = re.sub(r'\D', '', match)
            if len(normalized) >= 9:
                phones.add(normalized[-9:])
    return list(phones)


def extract_emails(text):
    """Extract emails."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text.lower())))[:3]


def extract_social(text):
    """Extract social media."""
    social = {"facebook": "", "instagram": ""}
    fb = re.search(r'(?:https?://)?(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+/?', text, re.I)
    if fb:
        url = fb.group(0)
        social["facebook"] = url if url.startswith('http') else 'https://' + url
    ig = re.search(r'(?:https?://)?(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+/?', text, re.I)
    if ig:
        url = ig.group(0)
        social["instagram"] = url if url.startswith('http') else 'https://' + url
    return social


def is_valid_website(url):
    """Check if URL is company website."""
    if not url:
        return False
    excluded = ['facebook.com', 'instagram.com', 'google.', 'panoramafirm.pl', 'pkt.pl']
    return not any(ex in url.lower() for ex in excluded)


def clean_text(text):
    """Clean whitespace."""
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

    # Find company links
    links = soup.select("a.addax-cs_hl_hit_company_name_click")
    if not links:
        links = soup.select("a[href*='.html'][href*='panoramafirm.pl']")

    seen = set()
    for link in links[:max_results * 2]:
        if len(businesses) >= max_results:
            break

        href = link.get("href", "")
        name = clean_text(link.get_text())

        if not name or not href or name in seen:
            continue
        seen.add(name)

        if not href.startswith("http"):
            href = urljoin(base_url, href)

        # Get details
        time.sleep(random.uniform(0.3, 0.7))
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
            html = detail.text

            # Address
            addr = dsoup.select_one("[itemprop='address'], .address, address")
            if addr:
                biz["address"] = clean_text(addr.get_text())

            # Phone
            phone = dsoup.select_one("a[href^='tel:']")
            if phone:
                biz["phone"] = phone.get("href", "").replace("tel:", "")
            if not biz["phone"]:
                phones = extract_phones(html)
                if phones:
                    biz["phone"] = phones[0]

            # Email
            email = dsoup.select_one("a[href^='mailto:']")
            if email:
                biz["email"] = email.get("href", "").replace("mailto:", "")
            if not biz["email"]:
                emails = extract_emails(html)
                if emails:
                    biz["email"] = emails[0]

            # Website
            www = dsoup.select_one("a[data-stat-id='www']")
            if www:
                href = www.get("href", "")
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
        # Parse query
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
