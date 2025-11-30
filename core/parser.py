import requests
from bs4 import BeautifulSoup
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def download_xml(url):
    logger.info(f"⬇️ Pobieranie XML z: {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content

def smart_parse_xml(url):
    try:
        content = download_xml(url)
        soup = BeautifulSoup(content, 'xml')
        
        # Obsługa różnych formatów (RSS, Atom, Ceneo, Google)
        items = soup.find_all(['item', 'product', 'o'])
        logger.info(f"📦 Znaleziono {len(items)} produktów.")

        parsed_products = []

        for item in items:
            def get_text(tags):
                for t in tags:
                    node = item.find(t)
                    if node and node.text:
                        return node.text.strip()
                return "Brak danych"

            # Fallback strategy - szukamy po różnych tagach
            title = get_text(['g:title', 'title', 'name', 'nazwa'])
            price = get_text(['g:price', 'price', 'cena', 'price_gross'])
            link = get_text(['link', 'g:link', 'url'])
            
            # Opis często jest brudny (HTML), więc go czyścimy
            desc_raw = get_text(['description', 'g:description', 'opis', 'desc'])
            desc_clean = BeautifulSoup(desc_raw, "html.parser").get_text()[:600] # Limit znaków dla wektora

            # Tworzymy dokument tekstowy do wektoryzacji
            text_content = (
                f"PRODUKT: {title}\n"
                f"CENA: {price}\n"
                f"LINK: {link}\n"
                f"OPIS: {desc_clean}"
            )
            
            # Dodajemy metadane (przydatne do filtrowania w przyszłości)
            metadata = {"source": url, "price": price, "link": link}
            
            parsed_products.append({"text": text_content, "meta": metadata})

        return parsed_products

    except Exception as e:
        logger.error(f"❌ Błąd parsowania XML: {e}")
        return []