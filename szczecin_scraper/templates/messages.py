"""
Szablony wiadomości do kontaktu z firmami.

Ten moduł generuje spersonalizowane wiadomości dla:
- Email
- Instagram DM
- Facebook Messenger
- LinkedIn

UWAGA: Automatyczne wysyłanie wiadomości może naruszać regulaminy platform!
Używaj odpowiedzialnie i zgodnie z RODO/przepisami o marketingu.
"""
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MessageTemplates:
    """Szablony wiadomości dla różnych kanałów."""

    # Dane nadawcy (dostosuj do swoich)
    sender_name: str = "Jan Kowalski"
    sender_company: str = "WebStudio Szczecin"
    sender_email: str = "kontakt@webstudio.pl"
    sender_phone: str = "+48 123 456 789"
    sender_website: str = "https://webstudio.pl"

    def generate_email(self, business: Dict, template: str = "standard") -> Dict:
        """
        Generuje email do firmy.

        Args:
            business: Dane firmy
            template: Typ szablonu (standard, short, premium)

        Returns:
            Dict z polami: subject, body, to
        """
        name = business.get("name", "Szanowni Państwo")
        industry = business.get("industry", "")

        templates = {
            "standard": self._email_standard(name, industry),
            "short": self._email_short(name, industry),
            "premium": self._email_premium(name, industry),
        }

        email_content = templates.get(template, templates["standard"])

        return {
            "to": business.get("email", ""),
            "subject": email_content["subject"],
            "body": email_content["body"],
            "business_name": name,
        }

    def _email_standard(self, name: str, industry: str) -> Dict:
        """Standardowy szablon emaila."""
        subject = f"Propozycja współpracy - strona internetowa dla {name}"

        body = f"""Dzień dobry,

Piszę do Państwa w imieniu {self.sender_company}.

Zauważyłem, że firma {name} nie posiada jeszcze własnej strony internetowej. W dzisiejszych czasach obecność online jest kluczowa dla rozwoju biznesu - ponad 80% klientów szuka usług i produktów w internecie przed podjęciem decyzji.

Specjalizujemy się w tworzeniu profesjonalnych stron internetowych dla firm z branży {industry or 'usługowej'}. Oferujemy:

✓ Nowoczesny, responsywny design dopasowany do Państwa marki
✓ Optymalizację pod wyszukiwarki (SEO) - żeby klienci łatwo Was znaleźli
✓ Łatwą edycję treści - bez znajomości programowania
✓ Integrację z mediami społecznościowymi
✓ Bezpłatną konsultację i wycenę

Czy moglibyśmy umówić się na krótką, niezobowiązującą rozmowę telefoniczną?

Z poważaniem,
{self.sender_name}
{self.sender_company}
Tel: {self.sender_phone}
Email: {self.sender_email}
{self.sender_website}

---
Jeśli nie są Państwo zainteresowani, przepraszam za wiadomość.
Proszę o odpowiedź "STOP" - więcej nie napiszę.
"""
        return {"subject": subject, "body": body}

    def _email_short(self, name: str, industry: str) -> Dict:
        """Krótki szablon emaila."""
        subject = f"Strona www dla {name}?"

        body = f"""Dzień dobry,

Czy zastanawialiście się Państwo nad stworzeniem strony internetowej dla {name}?

Pomagam lokalnym firmom ze Szczecina zaistnieć w internecie. Oferuję:
• Profesjonalną stronę od 1500 zł
• Gotową w 2 tygodnie
• Bezpłatną konsultację

Zainteresowani? Proszę o kontakt:
{self.sender_phone} | {self.sender_email}

Pozdrawiam,
{self.sender_name}
"""
        return {"subject": subject, "body": body}

    def _email_premium(self, name: str, industry: str) -> Dict:
        """Premium szablon - dla większych firm."""
        subject = f"Cyfrowa transformacja dla {name} - propozycja partnerstwa"

        body = f"""Szanowni Państwo,

Analizując rynek {industry or 'lokalnych usług'} w Szczecinie, zwróciłem uwagę na firmę {name} jako lidera w swojej branży.

Jako {self.sender_company}, specjalizujemy się w kompleksowej obecności online dla firm premium. Chciałbym zaproponować współpracę obejmującą:

1. STRONA INTERNETOWA
   - Indywidualny projekt graficzny
   - System rezerwacji/kontaktu online
   - Blog firmowy wspierający SEO

2. MARKETING CYFROWY
   - Pozycjonowanie w Google
   - Kampanie Google Ads
   - Zarządzanie social media

3. WSPARCIE TECHNICZNE
   - Hosting i bezpieczeństwo
   - Regularne aktualizacje
   - Wsparcie 24/7

Zapraszam na bezpłatną konsultację, podczas której przeanalizujemy Państwa potrzeby i przedstawię konkretne rozwiązania.

Czy mogę zadzwonić w tym tygodniu?

Z wyrazami szacunku,
{self.sender_name}
{self.sender_company}
{self.sender_phone}
{self.sender_website}
"""
        return {"subject": subject, "body": body}

    def generate_instagram_dm(self, business: Dict) -> str:
        """
        Generuje wiadomość na Instagram DM.
        Krótka i nieformalna.
        """
        name = business.get("name", "")

        return f"""Cześć! 👋

Prowadzę {self.sender_company} i pomagam lokalnym firmom ze Szczecina w tworzeniu stron internetowych.

Zauważyłem, że {name} nie ma jeszcze strony www. W dzisiejszych czasach to naprawdę pomaga dotrzeć do nowych klientów! 📱💻

Jeśli byłoby zainteresowanie, chętnie opowiem więcej. Bez zobowiązań!

Pozdrawiam,
{self.sender_name}
"""

    def generate_facebook_message(self, business: Dict) -> str:
        """
        Generuje wiadomość na Facebook Messenger.
        Przyjaźniejszy ton.
        """
        name = business.get("name", "")
        industry = business.get("industry", "")

        return f"""Dzień dobry!

Piszę z {self.sender_company} - zajmujemy się tworzeniem stron internetowych dla firm z regionu Szczecina.

Przeglądając {industry or 'lokalne firmy'}, trafiłem na {name}. Świetnie, że jesteście aktywni na Facebooku! 👍

Zastanawiałem się, czy rozważaliście Państwo własną stronę www? To świetne uzupełnienie profilu na FB - klienci mogą łatwo znaleźć wszystkie informacje, a Google pokazuje Was w wynikach wyszukiwania.

Jeśli temat jest ciekawy, chętnie porozmawiam - bez żadnych zobowiązań!

Pozdrawiam serdecznie,
{self.sender_name}
📞 {self.sender_phone}
"""

    def generate_linkedin_message(self, business: Dict) -> str:
        """
        Generuje wiadomość na LinkedIn.
        Profesjonalny ton B2B.
        """
        name = business.get("name", "")

        return f"""Dzień dobry,

Łączę się z przedstawicielami lokalnych firm ze Szczecina, którym mogę pomóc w rozwoju obecności online.

Zauważyłem, że {name} nie posiada jeszcze strony internetowej. W {self.sender_company} specjalizujemy się właśnie w tym - tworzymy profesjonalne strony, które pomagają firmom pozyskiwać nowych klientów.

Czy byłaby Pani/Pan zainteresowana krótką rozmową na ten temat?

Z poważaniem,
{self.sender_name}
{self.sender_company}
"""


class MessageGenerator:
    """
    Generator spersonalizowanych wiadomości dla listy firm.
    """

    def __init__(
        self,
        sender_name: str = None,
        sender_company: str = None,
        sender_email: str = None,
        sender_phone: str = None,
        sender_website: str = None
    ):
        """Inicjalizuje generator z danymi nadawcy."""
        self.templates = MessageTemplates(
            sender_name=sender_name or "Jan Kowalski",
            sender_company=sender_company or "WebStudio",
            sender_email=sender_email or "kontakt@example.com",
            sender_phone=sender_phone or "+48 123 456 789",
            sender_website=sender_website or "https://example.com"
        )

    def generate_all_messages(self, business: Dict) -> Dict:
        """
        Generuje wszystkie typy wiadomości dla firmy.

        Args:
            business: Dane firmy

        Returns:
            Dict ze wszystkimi wiadomościami
        """
        return {
            "business": business.get("name", ""),
            "email": self.templates.generate_email(business),
            "email_short": self.templates.generate_email(business, "short"),
            "instagram": self.templates.generate_instagram_dm(business),
            "facebook": self.templates.generate_facebook_message(business),
            "linkedin": self.templates.generate_linkedin_message(business),
        }

    def export_messages_to_file(
        self,
        businesses: list,
        output_path: str = "output/wiadomosci.txt"
    ):
        """
        Eksportuje wiadomości dla wszystkich firm do pliku.

        Args:
            businesses: Lista firm
            output_path: Ścieżka do pliku wyjściowego
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("WIADOMOŚCI DO WYSŁANIA\n")
            f.write(f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 70 + "\n\n")

            for i, business in enumerate(businesses, 1):
                messages = self.generate_all_messages(business)

                f.write(f"\n{'#' * 70}\n")
                f.write(f"# FIRMA {i}: {messages['business']}\n")
                f.write(f"{'#' * 70}\n\n")

                # Email
                email = messages["email"]
                if email.get("to"):
                    f.write("--- EMAIL ---\n")
                    f.write(f"Do: {email['to']}\n")
                    f.write(f"Temat: {email['subject']}\n\n")
                    f.write(email['body'])
                    f.write("\n\n")

                # Instagram
                if business.get("instagram"):
                    f.write("--- INSTAGRAM DM ---\n")
                    f.write(f"Profil: {business['instagram']}\n\n")
                    f.write(messages["instagram"])
                    f.write("\n\n")

                # Facebook
                if business.get("facebook"):
                    f.write("--- FACEBOOK MESSENGER ---\n")
                    f.write(f"Profil: {business['facebook']}\n\n")
                    f.write(messages["facebook"])
                    f.write("\n\n")

        print(f"Wiadomości zapisane do: {output_path}")


# Przykład użycia
if __name__ == "__main__":
    # Przykładowe dane firmy
    sample_business = {
        "name": "Restauracja Pod Lipą",
        "industry": "Restauracje",
        "email": "kontakt@podlipa.pl",
        "phone": "+48 91 123 4567",
        "facebook": "https://facebook.com/restauracjapodlipa",
        "instagram": "https://instagram.com/podlipa_szczecin",
    }

    # Generuj wiadomości
    generator = MessageGenerator(
        sender_name="Anna Nowak",
        sender_company="Digital Solutions Szczecin",
        sender_email="anna@digitalsolutions.pl",
        sender_phone="+48 500 100 200",
        sender_website="https://digitalsolutions.pl"
    )

    all_messages = generator.generate_all_messages(sample_business)

    print("=== EMAIL ===")
    print(f"Temat: {all_messages['email']['subject']}")
    print(all_messages['email']['body'])

    print("\n=== INSTAGRAM DM ===")
    print(all_messages['instagram'])
