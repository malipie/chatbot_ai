# Estetino AI Advisor - Serverless RAG Chatbot

Profesjonalny, skalowalny asystent sprzedażowy oparty na architekturze **RAG (Retrieval Augmented Generation)**, wdrożony w modelu Serverless na Google Cloud Run.

Projekt rozwiązuje problem nawigacji po ofercie e-commerce, pozwalając klientom pytać językiem naturalnym (np. *"Szukam eleganckich szpilek na wesele"*), zamiast korzystać ze skomplikowanych filtrów.

## Kluczowe Funkcje (Enterprise Grade)

* **Cloud-Native Vector Search:** Wykorzystuje **Qdrant Cloud** jako bazę wektorową, zapewniając błyskawiczny start aplikacji (brak indeksowania przy starcie kontenera) i trwałość danych.
* **Smart Caching (Redis):** Dwuwarstwowy system cache z **normalizacją zapytań** (Fuzzy Caching). Powtarzające się pytania są obsługiwane w <20ms bez kosztów OpenAI.
* **Prompt Engineering as Code:** Zarządzanie promptami i konfiguracją modelu (temperatura, wersja GPT) odbywa się zdalnie przez **LangFuse**, bez konieczności redeployowania aplikacji.
* **Product Deduplication:** Autorski algorytm w Pythonie filtrujący warianty produktów (rozmiary), aby zmaksymalizować jakość kontekstu przekazywanego do LLM.
* **Hybrid UI:**
    * Pełnoekranowy panel dla obsługi klienta (**Chainlit**).
    * Lekki, embedowany Widget JS dla sklepu (**FastAPI Endpoint**).
* **Observability:** Pełne śledzenie tokenów, kosztów i jakości odpowiedzi w LangFuse Tracing.

## Stack Technologiczny

* **Backend:** Python 3.11, FastAPI, Uvicorn
* **AI Orchestration:** LangChain, OpenAI (GPT-4o / GPT-4o-mini)
* **Vector Database:** Qdrant Cloud (Managed)
* **Cache:** Redis Cloud
* **LLMOps:** LangFuse (Tracing & Prompt Management)
* **Infrastructure:** Docker, Google Cloud Run (Serverless)

## Konfiguracja i Uruchomienie

### Wymagania
* Docker & Docker Compose
* Klucze API: OpenAI, LangFuse, Qdrant, Redis

### 1. Konfiguracja środowiska
Utwórz plik `.env` na podstawie szablonu:

OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=[https://cloud.langfuse.com](https://cloud.langfuse.com)
QDRANT_URL=[https://twoj-klaster.qdrant.io](https://twoj-klaster.qdrant.io)
QDRANT_API_KEY=...
REDIS_URL=redis://:haslo@adres:port
ALLOWED_ORIGINS=[https://twojsklep.pl](https://twojsklep.pl)
DOCKER_ENV=true

### 2. Migracja Danych (Ingest)
Ponieważ aplikacja jest bezstanowa (stateless), indeksowanie odbywa się osobnym skryptem. Uruchom go raz, aby "nakarmić" bazę Qdrant:

pip install -r requirements.txt
python ingest_to_qdrant.py

### 3. Uruchomienie (Docker Compose)
docker-compose up --build

### 4. Wdrożenie na Produkcję (Google Cloud Run)

gcloud builds submit --tag gcr.io/TWOJE-ID/bot .
gcloud run deploy estetino-bot --image gcr.io/TWOJE-ID/bot ...

