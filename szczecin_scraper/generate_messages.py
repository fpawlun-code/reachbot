#!/usr/bin/env python3
"""
Generator wiadomości do kontaktu z firmami.

Wczytuje dane firm z pliku Excel/CSV i generuje spersonalizowane
wiadomości do wysłania przez email, Instagram, Facebook, LinkedIn.

Użycie:
    python generate_messages.py output/firmy_szczecin_20240115.xlsx
    python generate_messages.py output/firmy.csv --format txt
    python generate_messages.py output/firmy.xlsx --sender-name "Jan Kowalski"
"""
import argparse
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

from templates.messages import MessageGenerator


def load_businesses(filepath: str) -> list:
    """Wczytuje dane firm z pliku."""
    path = Path(filepath)

    if path.suffix == ".csv":
        df = pd.read_csv(filepath, sep=";", encoding="utf-8-sig")
    elif path.suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(filepath)
    elif path.suffix == ".json":
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("businesses", data)
    else:
        raise ValueError(f"Nieobsługiwany format pliku: {path.suffix}")

    # Konwertuj DataFrame na listę słowników
    # Mapuj polskie nazwy kolumn na angielskie
    column_mapping = {
        "Nazwa firmy": "name",
        "Branża": "industry",
        "Adres": "address",
        "Telefon": "phone",
        "Email": "email",
        "Facebook": "facebook",
        "Instagram": "instagram",
        "LinkedIn": "linkedin",
        "Strona WWW": "website",
        "Ma stronę?": "has_website",
        "Źródło": "source",
    }

    df = df.rename(columns=column_mapping)
    return df.to_dict("records")


def main():
    parser = argparse.ArgumentParser(
        description="Generator wiadomości do firm bez stron internetowych"
    )

    parser.add_argument(
        "input_file",
        help="Plik z danymi firm (Excel, CSV lub JSON)"
    )

    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Plik wyjściowy (domyślnie: wiadomosci_YYYYMMDD.txt)"
    )

    parser.add_argument(
        "--format", "-f",
        choices=["txt", "json", "html"],
        default="txt",
        help="Format wyjściowy (domyślnie: txt)"
    )

    parser.add_argument(
        "--sender-name",
        default="Jan Kowalski",
        help="Imię i nazwisko nadawcy"
    )

    parser.add_argument(
        "--sender-company",
        default="WebStudio Szczecin",
        help="Nazwa firmy nadawcy"
    )

    parser.add_argument(
        "--sender-email",
        default="kontakt@webstudio.pl",
        help="Email nadawcy"
    )

    parser.add_argument(
        "--sender-phone",
        default="+48 123 456 789",
        help="Telefon nadawcy"
    )

    parser.add_argument(
        "--sender-website",
        default="https://webstudio.pl",
        help="Strona nadawcy"
    )

    parser.add_argument(
        "--template",
        choices=["standard", "short", "premium"],
        default="standard",
        help="Szablon emaila (domyślnie: standard)"
    )

    args = parser.parse_args()

    # Wczytaj dane
    print(f"Wczytywanie danych z: {args.input_file}")
    businesses = load_businesses(args.input_file)
    print(f"Znaleziono {len(businesses)} firm")

    # Filtruj firmy z kontaktem
    contactable = [
        b for b in businesses
        if b.get("email") or b.get("facebook") or b.get("instagram")
    ]
    print(f"Firmy z dostępnym kontaktem: {len(contactable)}")

    if not contactable:
        print("Brak firm z danymi kontaktowymi!")
        return

    # Inicjalizuj generator
    generator = MessageGenerator(
        sender_name=args.sender_name,
        sender_company=args.sender_company,
        sender_email=args.sender_email,
        sender_phone=args.sender_phone,
        sender_website=args.sender_website
    )

    # Generuj wiadomości
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.output or f"output/wiadomosci_{timestamp}.{args.format}"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    if args.format == "txt":
        _export_txt(generator, contactable, output_file, args.template)
    elif args.format == "json":
        _export_json(generator, contactable, output_file)
    elif args.format == "html":
        _export_html(generator, contactable, output_file, args.template)

    print(f"\nWiadomości zapisane do: {output_file}")
    print(f"Liczba wygenerowanych wiadomości: {len(contactable)}")


def _export_txt(generator, businesses, output_file, template):
    """Eksportuje wiadomości do pliku tekstowego."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("WIADOMOŚCI DO WYSŁANIA\n")
        f.write(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Szablon: {template}\n")
        f.write("=" * 70 + "\n\n")

        for i, business in enumerate(businesses, 1):
            f.write(f"\n{'#' * 70}\n")
            f.write(f"# {i}. {business.get('name', 'Brak nazwy')}\n")
            f.write(f"# Branża: {business.get('industry', '-')}\n")
            f.write(f"{'#' * 70}\n\n")

            # Email
            if business.get("email"):
                email = generator.templates.generate_email(business, template)
                f.write("--- EMAIL ---\n")
                f.write(f"Do: {business['email']}\n")
                f.write(f"Temat: {email['subject']}\n")
                f.write("-" * 40 + "\n")
                f.write(email['body'])
                f.write("\n\n")

            # Instagram
            if business.get("instagram"):
                f.write("--- INSTAGRAM DM ---\n")
                f.write(f"Profil: {business['instagram']}\n")
                f.write("-" * 40 + "\n")
                f.write(generator.templates.generate_instagram_dm(business))
                f.write("\n\n")

            # Facebook
            if business.get("facebook"):
                f.write("--- FACEBOOK ---\n")
                f.write(f"Profil: {business['facebook']}\n")
                f.write("-" * 40 + "\n")
                f.write(generator.templates.generate_facebook_message(business))
                f.write("\n\n")

            f.write("\n")


def _export_json(generator, businesses, output_file):
    """Eksportuje wiadomości do pliku JSON."""
    all_messages = []

    for business in businesses:
        messages = generator.generate_all_messages(business)
        all_messages.append(messages)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "count": len(all_messages),
            "messages": all_messages
        }, f, ensure_ascii=False, indent=2)


def _export_html(generator, businesses, output_file, template):
    """Eksportuje wiadomości do pliku HTML."""
    html = """<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wiadomości do wysłania</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        .business { border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 8px; }
        .business h2 { color: #333; margin-top: 0; }
        .channel { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 4px; }
        .channel h3 { margin-top: 0; color: #666; }
        .message { white-space: pre-wrap; font-family: monospace; background: white; padding: 10px; }
        .meta { color: #888; font-size: 0.9em; }
        .copy-btn { background: #4CAF50; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 4px; }
        .copy-btn:hover { background: #45a049; }
    </style>
</head>
<body>
    <h1>Wiadomości do wysłania</h1>
    <p class="meta">Wygenerowano: """ + datetime.now().strftime('%Y-%m-%d %H:%M') + f"""</p>
    <p class="meta">Liczba firm: {len(businesses)}</p>
"""

    for i, business in enumerate(businesses, 1):
        html += f"""
    <div class="business">
        <h2>{i}. {business.get('name', 'Brak nazwy')}</h2>
        <p class="meta">Branża: {business.get('industry', '-')} | Adres: {business.get('address', '-')}</p>
"""

        if business.get("email"):
            email = generator.templates.generate_email(business, template)
            html += f"""
        <div class="channel">
            <h3>📧 Email</h3>
            <p><strong>Do:</strong> {business['email']}</p>
            <p><strong>Temat:</strong> {email['subject']}</p>
            <div class="message">{email['body']}</div>
        </div>
"""

        if business.get("instagram"):
            dm = generator.templates.generate_instagram_dm(business)
            html += f"""
        <div class="channel">
            <h3>📸 Instagram DM</h3>
            <p><strong>Profil:</strong> <a href="{business['instagram']}" target="_blank">{business['instagram']}</a></p>
            <div class="message">{dm}</div>
        </div>
"""

        if business.get("facebook"):
            fb = generator.templates.generate_facebook_message(business)
            html += f"""
        <div class="channel">
            <h3>👤 Facebook</h3>
            <p><strong>Profil:</strong> <a href="{business['facebook']}" target="_blank">{business['facebook']}</a></p>
            <div class="message">{fb}</div>
        </div>
"""

        html += "    </div>\n"

    html += """
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
