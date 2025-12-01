import os
import logging
import hashlib
import re
import bleach
from redis.asyncio import Redis
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from core.parser import smart_parse_xml
from core.settings import settings

logger = logging.getLogger(__name__)

PERSIST_DIR = "./chroma_db"

# --- ZMIENNE GLOBALNE ---
_vector_store = None
_redis_client = None

# --- POMOCNICZE: NORMALIZACJA TEKSTU ---
def normalize_query(text: str) -> str:
    """Zwiększa szansę na trafienie w Cache (usuwa interpunkcję, sortuje słowa)."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    words.sort()
    return " ".join(words)

# --- REDIS (Singleton) ---
async def get_redis():
    global _redis_client
    if _redis_client is None:
        # Wykrywanie czy jesteśmy w Dockerze (nazwa hosta "redis") czy lokalnie ("localhost")
        redis_host = "redis" if os.environ.get("DOCKER_ENV") else "localhost"
        # Port 6379 to port WEWNĘTRZNY kontenera (niezależnie od mapowania na zewnątrz)
        _redis_client = Redis.from_url(f"redis://{redis_host}:6379", decode_responses=True)
    return _redis_client

# --- VECTOR STORE (Singleton) ---
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        logger.info("⚙️ Inicjalizacja ChromaDB...")
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", 
            api_key=settings.openai_api_key,
            check_embedding_ctx_length=False 
        )
        _vector_store = Chroma(
            collection_name="estetino_products",
            embedding_function=embeddings,
            persist_directory=PERSIST_DIR
        )
    return _vector_store

async def initialize_database():
    """Startowa inicjalizacja bazy."""
    try:
        store = get_vector_store()
        try:
            collection_data = store.get(limit=1) 
            count = len(collection_data['ids'])
        except Exception:
            count = 0
            
        if count > 0:
            logger.info(f"✅ Baza wektorowa załadowana ({count}+ elementów).")
            return 
        else:
            logger.info("📭 Baza pusta. Rozpoczynam indeksowanie...")

    except Exception as e:
        logger.warning(f"⚠️ Problem z dostępem do bazy: {e}")

    raw_data = smart_parse_xml(settings.xml_url)
    if not raw_data:
        logger.warning("⚠️ Nie udało się pobrać XML.")
        return

    documents = [
        Document(page_content=p['text'], metadata=p['meta']) 
        for p in raw_data
    ]
    
    store = get_vector_store()
    batch_size = 100
    logger.info(f"📦 Dodaję {len(documents)} produktów do bazy...")
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        store.add_documents(batch)
        if i % 500 == 0:
            logger.info(f"✅ Przetworzono {i} / {len(documents)}")
            
    logger.info("🎉 Indeksowanie zakończone!")

# --- GŁÓWNA LOGIKA RAG ---
async def get_rag_response(user_query: str):
    
    # 1. CACHE (REDIS)
    cache_key = ""
    redis = None
    try:
        redis = await get_redis()
        normalized_q = normalize_query(user_query)
        query_hash = hashlib.md5(normalized_q.encode()).hexdigest()
        cache_key = f"rag_response:{query_hash}"
        
        cached_response = await redis.get(cache_key)
        if cached_response:
            logger.info(f"⚡ Cache Hit! (Klucz: '{normalized_q}')")
            return cached_response
    except Exception as e:
        logger.warning(f"⚠️ Redis error (pomijam cache): {e}")

    # 2. RETRIEVAL (DEDUPLIKACJA)
    context_text = ""
    try:
        vector_store = get_vector_store()
        docs = vector_store.similarity_search(user_query, k=30)
        
        unique_docs = []
        seen_titles = set()
        
        for doc in docs:
            content = doc.page_content
            title = content.split('\n')[0] 
            if title not in seen_titles:
                unique_docs.append(doc)
                seen_titles.add(title)
            if len(unique_docs) >= 8:
                break
        
        context_text = "\n\n".join([d.page_content for d in unique_docs])
        # print(f"📊 DEBUG: Pobranych: {len(docs)} | Unikalnych: {len(unique_docs)}")
        
    except Exception as e:
        logger.error(f"❌ Błąd ChromaDB: {e}")
        context_text = "BRAK DANYCH."

    if not context_text: 
        context_text = "BRAK PRODUKTÓW."

    # 3. KONFIGURACJA MODELU (LANGFUSE)
    # Domyślne wartości (Fallback)
    system_msg = "Jesteś asystentem sklepu Estetino. Odpowiadaj na podstawie kontekstu."
    user_msg = f"{user_query}"
    model_name = "gpt-4o-mini"
    temperature = 0
    callbacks = []

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        
        # Handler do śledzenia (Tracing)
        callbacks.append(CallbackHandler())
        
        # Klient Langfuse
        lf = Langfuse()
        
        # Pobieranie promptu
        lf_prompt = lf.get_prompt("estetino-advisor")
        
        # Kompilacja treści
        compiled = lf_prompt.compile(
            context=context_text,
            question=user_query,
            shop_name=settings.shop_name
        )
        for msg in compiled:
            if msg['role'] == 'system': system_msg = msg['content']
            elif msg['role'] == 'user': user_msg = msg['content']
            
        # Pobieranie configu (Model/Temp)
        if lf_prompt.config:
            model_name = lf_prompt.config.get("model", model_name)
            temperature = float(lf_prompt.config.get("temperature", temperature))
            
        logger.info(f"🤖 Config z Langfuse: Model={model_name}, Temp={temperature}")
            
    except Exception as e:
        logger.warning(f"⚠️ Langfuse error (używam fallback): {e}")

    # 4. OPENAI (ASYNC GENERATION)
    try:
        model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.openai_api_key
        )
        
        # Wywołanie z callbackami
        response = await model.ainvoke(
            [
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg)
            ],
            config={"callbacks": callbacks}
        )
        raw_answer = response.content
    except Exception as e:
        logger.error(f"❌ OpenAI error: {e}")
        return "Przepraszam, mam chwilowy problem z połączeniem."

    # 5. SANITYZACJA (Bleach)
    clean_answer = bleach.clean(
        raw_answer, 
        tags=['b', 'i', 'strong', 'em', 'a', 'br', 'p', 'ul', 'li'], 
        attributes={'a': ['href', 'target']}
    )

    # 6. ZAPIS DO CACHE
    try:
        if redis:
            # Cache na 24h (86400 sekund)
            await redis.setex(cache_key, 86400, clean_answer)
    except Exception:
        pass
    
    return clean_answer