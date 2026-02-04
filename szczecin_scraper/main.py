#!/usr/bin/env python3
"""
Szczecin Business Scraper - Główny skrypt

Skanuje rynek w Szczecinie w poszukiwaniu firm bez stron internetowych.
Zbiera dane kontaktowe i eksportuje je do pliku.

Użycie:
    python main.py                          # Pełne skanowanie
    python main.py --industries restauracje kawiarnie
    python main.py --max-results 50
    python main.py --output-format docx
    python main.py --source panorama         # Tylko Panorama Firm
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
from tqdm import tqdm

# Dodaj katalog główny do ścieżki
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    INDUSTRIES, CITY, MAX_BUSINESSES, OUTPUT_FORMAT, OUTPUT_DIR
)
from scrapers.google_maps import GoogleMapsScraper
from scrapers.panorama_firm import PanoramaFirmScraper
from scrapers.pkt_scraper import PKTScraper
from scrapers.website_checker import WebsiteChecker, has_no_website
from utils.exporter import DataExporter
from utils.helpers import random_delay

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(OUTPUT_DIR / "scraper.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


class SzczecinBusinessScraper:
    """
    Główna klasa orkiestrująca skanowanie firm w Szczecinie.
    """

    def __init__(
        self,
        industries: List[str] = None,
        max_results_per_industry: int = 20,
        sources: List[str] = None,
        verify_websites: bool = True
    ):
        """
        Inicjalizuje scraper.

        Args:
            industries: Lista branż do skanowania
            max_results_per_industry: Max wyników na branżę
            sources: Źródła danych ['google', 'panorama', 'pkt']
            verify_websites: Czy weryfikować strony www
        """
        self.industries = industries or INDUSTRIES
        self.max_results = max_results_per_industry
        self.sources = sources or ["panorama", "pkt"]  # Google wymaga API
        self.verify_websites = verify_websites

        # Inicjalizuj scrapery
        self.scrapers = {}
        if "google" in self.sources:
            self.scrapers["google"] = GoogleMapsScraper()
        if "panorama" in self.sources:
            self.scrapers["panorama"] = PanoramaFirmScraper()
        if "pkt" in self.sources:
            self.scrapers["pkt"] = PKTScraper()

        self.website_checker = WebsiteChecker() if verify_websites else None
        self.exporter = DataExporter()

        # Zebrane dane
        self.all_businesses: List[Dict] = []
        self.businesses_without_website: List[Dict] = []
        self.seen_names: Set[str] = set()  # Deduplikacja

    def run(self) -> List[Dict]:
        """
        Uruchamia pełne skanowanie.

        Returns:
            Lista firm bez stron internetowych
        """
        logger.info("=" * 60)
        logger.info("SZCZECIN BUSINESS SCRAPER - START")
        logger.info(f"Branże: {', '.join(self.industries)}")
        logger.info(f"Źródła: {', '.join(self.sources)}")
        logger.info(f"Max wyników/branżę: {self.max_results}")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Skanuj każdą branżę
        for industry in tqdm(self.industries, desc="Branże"):
            logger.info(f"\n>>> Skanuję branżę: {industry}")
            self._scan_industry(industry)
            random_delay(2, 4)

        # Weryfikuj strony www
        if self.verify_websites and self.all_businesses:
            logger.info("\n>>> Weryfikacja stron internetowych...")
            self._verify_websites()

        # Filtruj firmy bez stron
        self.businesses_without_website = [
            b for b in self.all_businesses if not b.get("has_website", True)
        ]

        # Podsumowanie
        elapsed = datetime.now() - start_time
        logger.info("\n" + "=" * 60)
        logger.info("PODSUMOWANIE")
        logger.info("=" * 60)
        logger.info(f"Czas skanowania: {elapsed}")
        logger.info(f"Wszystkie firmy: {len(self.all_businesses)}")
        logger.info(f"Firmy BEZ strony www: {len(self.businesses_without_website)}")
        logger.info("=" * 60)

        return self.businesses_without_website

    def _scan_industry(self, industry: str):
        """Skanuje pojedynczą branżę we wszystkich źródłach."""
        industry_businesses = []

        for source_name, scraper in self.scrapers.items():
            logger.info(f"  Źródło: {source_name}")

            try:
                for business in scraper.search_businesses(
                    industry=industry,
                    city=CITY,
                    max_results=self.max_results
                ):
                    # Deduplikacja po nazwie
                    name_key = business.name.lower().strip()
                    if name_key in self.seen_names:
                        continue

                    self.seen_names.add(name_key)
                    biz_dict = business.to_dict() if hasattr(business, 'to_dict') else business

                    # Dodaj branżę jeśli brakuje
                    if not biz_dict.get("industry"):
                        biz_dict["industry"] = industry

                    industry_businesses.append(biz_dict)
                    logger.debug(f"    + {business.name}")

            except Exception as e:
                logger.error(f"  Błąd źródła {source_name}: {e}")
                continue

            random_delay(1, 2)

        logger.info(f"  Znaleziono: {len(industry_businesses)} firm")
        self.all_businesses.extend(industry_businesses)

    def _verify_websites(self):
        """Weryfikuje strony www wszystkich firm."""
        logger.info(f"Weryfikuję {len(self.all_businesses)} stron...")

        for i, business in enumerate(tqdm(self.all_businesses, desc="Weryfikacja")):
            website = business.get("website", "")

            if not website:
                business["has_website"] = False
                continue

            try:
                status = self.website_checker.check_website(website)
                business["has_website"] = status.is_active and status.is_company_site

                # Jeśli strona nieaktywna, spróbuj wyciągnąć kontakty z innych źródeł
                if not business["has_website"]:
                    logger.debug(f"  Strona nieaktywna: {business['name']} - {website}")

            except Exception as e:
                logger.debug(f"  Błąd weryfikacji {website}: {e}")
                business["has_website"] = False

            # Rate limiting
            if i % 10 == 0:
                random_delay(1, 2)

    def export_results(
        self,
        format: str = None,
        filename: str = None,
        only_without_website: bool = True
    ) -> Path:
        """
        Eksportuje wyniki do pliku.

        Args:
            format: Format wyjściowy (csv, xlsx, docx)
            filename: Nazwa pliku
            only_without_website: Tylko firmy bez strony

        Returns:
            Ścieżka do pliku
        """
        format = format or OUTPUT_FORMAT
        data = self.businesses_without_website if only_without_website else self.all_businesses

        if not data:
            logger.warning("Brak danych do eksportu!")
            return None

        filepath = self.exporter.export(data, filename, format)
        logger.info(f"Dane wyeksportowane do: {filepath}")

        # Eksportuj też podsumowanie
        summary_path = self.exporter.export_summary(data)
        logger.info(f"Podsumowanie: {summary_path}")

        return filepath

    def close(self):
        """Zamyka zasoby."""
        for scraper in self.scrapers.values():
            if hasattr(scraper, 'close'):
                scraper.close()


def main():
    """Główna funkcja CLI."""
    parser = argparse.ArgumentParser(
        description="Szczecin Business Scraper - znajdź firmy bez stron www"
    )

    parser.add_argument(
        "--industries", "-i",
        nargs="+",
        default=None,
        help="Branże do skanowania (domyślnie: wszystkie z config)"
    )

    parser.add_argument(
        "--max-results", "-m",
        type=int,
        default=20,
        help="Max wyników na branżę (domyślnie: 20)"
    )

    parser.add_argument(
        "--sources", "-s",
        nargs="+",
        choices=["google", "panorama", "pkt"],
        default=["panorama", "pkt"],
        help="Źródła danych (domyślnie: panorama, pkt)"
    )

    parser.add_argument(
        "--output-format", "-f",
        choices=["csv", "xlsx", "docx", "json"],
        default="xlsx",
        help="Format wyjściowy (domyślnie: xlsx)"
    )

    parser.add_argument(
        "--output-file", "-o",
        default=None,
        help="Nazwa pliku wyjściowego (bez rozszerzenia)"
    )

    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Pomiń weryfikację stron www (szybsze)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Eksportuj wszystkie firmy (nie tylko bez strony)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowe logi"
    )

    args = parser.parse_args()

    # Ustaw poziom logowania
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Uruchom scraper
    scraper = SzczecinBusinessScraper(
        industries=args.industries,
        max_results_per_industry=args.max_results,
        sources=args.sources,
        verify_websites=not args.no_verify
    )

    try:
        results = scraper.run()

        if results or args.all:
            scraper.export_results(
                format=args.output_format,
                filename=args.output_file,
                only_without_website=not args.all
            )

            print(f"\n✓ Znaleziono {len(results)} firm bez strony internetowej")
            print(f"✓ Wyniki zapisano w katalogu: {OUTPUT_DIR}")
        else:
            print("\n✗ Nie znaleziono firm bez strony internetowej")

    except KeyboardInterrupt:
        print("\n\nPrzerwano przez użytkownika")
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
