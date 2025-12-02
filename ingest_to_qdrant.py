import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models # models jest potrzebne do konfiguracji
from langchain_core.documents import Document
from core.parser import smart_parse_xml
from core.settings import settings 

def ingest():
    print("🚀 Rozpoczynam migrację danych do Qdrant Cloud...")

    # --- 1. DIAGNOSTYKA I ŁADOWANIE ZMIENNYCH ---
    print("🔍 Diagnostyka .env:")
    env_path = find_dotenv()
    if not env_path:
        print("❌ BŁĄD KRYTYCZNY: Python w ogóle nie widzi pliku .env!")
    else:
        load_dotenv(env_path, override=True)

    url = os.environ.get("QDRANT_URL")
    key = os.environ.get("QDRANT_API_KEY")
    collection_name = settings.collection_name

    if not url or not key:
        print("❌ Błąd: Brak danych Qdrant w .env")
        return

    # --- 2. TWORZENIE KLIENTA ---
    try:
        client = QdrantClient(url=url, api_key=key)
        print("✅ Klient Qdrant zainicjalizowany.")
    except Exception as e:
        print(f"❌ Błąd inicjalizacji klienta Qdrant: {e}")
        return

    # --- 2.5. TWORZENIE KOLEKCJI (To naprawia błąd 404!) ---
    # Sprawdzamy czy kolekcja istnieje. Jeśli nie - tworzymy ją.
    if not client.collection_exists(collection_name):
        print(f"🔨 Kolekcja '{collection_name}' nie istnieje. Tworzę ją...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # 👈 WAŻNE: To jest wymiar dla text-embedding-3-small
                distance=models.Distance.COSINE
            )
        )
        print("✅ Kolekcja utworzona pomyślnie.")
    else:
        print(f"ℹ️ Kolekcja '{collection_name}' już istnieje. Dopisywanie danych...")

    # --- 3. POBRANIE DANYCH ---
    raw_data = smart_parse_xml(settings.xml_url)
    if not raw_data:
        print("❌ Błąd: Nie udało się pobrać produktów z XML.")
        return

    documents = [
        Document(page_content=p['text'], metadata=p['meta']) 
        for p in raw_data
    ]
    print(f"📦 Znaleziono {len(documents)} produktów. Przygotowuję wektoryzację...")

    # --- 4. WEKTORYZACJA I UPLOAD ---
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small", 
        api_key=settings.openai_api_key,
        check_embedding_ctx_length=False
    )
    
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    
    # Upload Batchami
    batch_size = 100
    total = len(documents)
    
    print(f"📡 Wysyłanie do kolekcji: {collection_name}")
    
    for i in range(0, total, batch_size):
        batch = documents[i:i+batch_size]
        vector_store.add_documents(batch)
        print(f"✅ Przesłano partię {i}-{min(i+batch_size, total)} / {total}")

    print("🎉 SUKCES! Baza Qdrant jest gotowa.")

if __name__ == "__main__":
    ingest()