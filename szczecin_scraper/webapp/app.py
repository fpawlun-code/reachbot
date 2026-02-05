#!/usr/bin/env python3
"""
Szczecin Business Scraper - Web Application
Prosty interfejs webowy do skanowania firm bez stron internetowych.
"""
import os
import sys
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, Response

# Dodaj katalog główny do ścieżki
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDUSTRIES, OUTPUT_DIR, CITY
from scrapers.panorama_firm import PanoramaFirmScraper
from scrapers.website_checker import WebsiteChecker
from utils.exporter import DataExporter
from utils.helpers import random_delay
from templates.messages import MessageGenerator

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Przechowywanie zadań skanowania
scan_jobs = {}


class ScanJob:
    """Reprezentuje zadanie skanowania."""

    def __init__(self, job_id: str, industries: list, max_results: int):
        self.job_id = job_id
        self.industries = industries
        self.max_results = max_results
        self.status = "pending"  # pending, running, completed, error
        self.progress = 0
        self.current_industry = ""
        self.businesses = []
        self.businesses_without_website = []
        self.error = None
        self.output_file = None
        self.started_at = None
        self.completed_at = None

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "current_industry": self.current_industry,
            "total_found": len(self.businesses),
            "without_website": len(self.businesses_without_website),
            "error": self.error,
            "output_file": self.output_file,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def run_scan(job: ScanJob):
    """Wykonuje skanowanie w tle."""
    try:
        job.status = "running"
        job.started_at = datetime.now()

        scraper = PanoramaFirmScraper()
        checker = WebsiteChecker(timeout=5)
        seen_names = set()

        total_industries = len(job.industries)

        for idx, industry in enumerate(job.industries):
            job.current_industry = industry
            job.progress = int((idx / total_industries) * 80)  # 80% na skanowanie

            try:
                for business in scraper.search_businesses(
                    industry=industry,
                    city=CITY,
                    max_results=job.max_results
                ):
                    name_key = business.name.lower().strip()
                    if name_key in seen_names:
                        continue

                    seen_names.add(name_key)
                    biz_dict = business.to_dict()
                    biz_dict["industry"] = industry
                    job.businesses.append(biz_dict)

            except Exception as e:
                print(f"Error scanning {industry}: {e}")
                continue

        # Weryfikacja stron www
        job.current_industry = "Weryfikacja stron..."
        job.progress = 85

        for i, biz in enumerate(job.businesses):
            website = biz.get("website", "")
            if not website:
                biz["has_website"] = False
            else:
                try:
                    status = checker.check_website(website)
                    biz["has_website"] = status.is_active and status.is_company_site
                except Exception:
                    biz["has_website"] = False

            if i % 5 == 0:
                job.progress = 85 + int((i / len(job.businesses)) * 10)

        # Filtruj firmy bez stron
        job.businesses_without_website = [
            b for b in job.businesses if not b.get("has_website", True)
        ]

        # Eksportuj wyniki
        job.current_industry = "Eksport wyników..."
        job.progress = 95

        if job.businesses_without_website:
            exporter = DataExporter()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"firmy_szczecin_{timestamp}"
            filepath = exporter.export(job.businesses_without_website, filename, "xlsx")
            job.output_file = str(filepath)

        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.now()
        job.current_industry = ""

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.completed_at = datetime.now()


@app.route("/")
def index():
    """Strona główna."""
    return render_template("index.html", industries=INDUSTRIES)


@app.route("/api/scan/start", methods=["POST"])
def start_scan():
    """Rozpoczyna nowe skanowanie."""
    data = request.json
    industries = data.get("industries", [])
    max_results = int(data.get("max_results", 10))

    if not industries:
        return jsonify({"error": "Wybierz przynajmniej jedną branżę"}), 400

    # Utwórz nowe zadanie
    job_id = str(uuid.uuid4())[:8]
    job = ScanJob(job_id, industries, max_results)
    scan_jobs[job_id] = job

    # Uruchom skanowanie w tle
    thread = threading.Thread(target=run_scan, args=(job,))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/api/scan/status/<job_id>")
def scan_status(job_id):
    """Zwraca status skanowania."""
    job = scan_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Nie znaleziono zadania"}), 404

    return jsonify(job.to_dict())


@app.route("/api/scan/results/<job_id>")
def scan_results(job_id):
    """Zwraca wyniki skanowania."""
    job = scan_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Nie znaleziono zadania"}), 404

    return jsonify({
        "businesses": job.businesses_without_website,
        "total": len(job.businesses_without_website)
    })


@app.route("/api/scan/download/<job_id>")
def download_results(job_id):
    """Pobiera plik z wynikami."""
    job = scan_jobs.get(job_id)
    if not job or not job.output_file:
        return jsonify({"error": "Brak pliku do pobrania"}), 404

    return send_file(
        job.output_file,
        as_attachment=True,
        download_name=os.path.basename(job.output_file)
    )


@app.route("/api/messages/generate", methods=["POST"])
def generate_messages():
    """Generuje wiadomości dla wybranych firm."""
    data = request.json
    businesses = data.get("businesses", [])
    sender = data.get("sender", {})

    generator = MessageGenerator(
        sender_name=sender.get("name", "Jan Kowalski"),
        sender_company=sender.get("company", "WebStudio"),
        sender_email=sender.get("email", "kontakt@webstudio.pl"),
        sender_phone=sender.get("phone", "+48 123 456 789"),
        sender_website=sender.get("website", "https://webstudio.pl")
    )

    messages = []
    for biz in businesses:
        msg = generator.generate_all_messages(biz)
        messages.append(msg)

    return jsonify({"messages": messages})


@app.route("/messages")
def messages_page():
    """Strona generatora wiadomości."""
    return render_template("messages.html")


if __name__ == "__main__":
    print("=" * 50)
    print("Szczecin Business Scraper - Web App")
    print("=" * 50)
    print("Otwórz w przeglądarce: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
