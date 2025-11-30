# AI Advisor

Inteligentny asystent sprzedażowy typu RAG (Retrieval Augmented Generation) dla sklepu e-commerce.

## Kluczowe funkcje
* **Smart RAG:** Wyszukiwanie semantyczne (OpenAI Embeddings + ChromaDB) z autorską logiką deduplikacji wariantów produktów (rozmiarów).
* **Hybrid UI:** Działa jednocześnie jako pełnoekranowy czat (Chainlit) oraz API dla widgetu JS na stronie sklepu.
* **Prompt Management:** Prompty zarządzane zdalnie przez LangFuse (z lokalnym fallbackiem).
* **Observability:** Pełne śledzenie rozmów i kosztów tokenów w LangFuse.

## Stack technologiczny
* **Python 3.11+**
* **LangChain & OpenAI GPT-4o-mini**
* **ChromaDB** (Vector Store)
* **Chainlit** (UI/UX)
* **LangFuse** (LLM Ops)
* **FastAPI** (Backend API)

## Uruchomienie
1. Skonfiguruj `.env` (patrz `.env.example`).
2. Zainstaluj zależności: `pip install -r requirements.txt`.
3. Uruchom: `chainlit run main.py`.