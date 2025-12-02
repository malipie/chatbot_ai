import os
import logging
import hashlib
import re
import bleach
import time
from redis.asyncio import Redis
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_core.messages import SystemMessage, HumanMessage
from core.parser import smart_parse_xml
from core.settings import settings

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ZMIENNE GLOBALNE ---
_vector_store = None
_redis_client = None

def normalize_query(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    words.sort()
    return " ".join(words)

async def get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL")
        try:
            if redis_url:
                logger.info("🔌 [REDIS] Łączenie (Produkcja)...")
                _redis_client = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
            else:
                host = "redis" if os.environ.get("DOCKER_ENV") else "localhost"
                logger.info(f"🔌 [REDIS] Łączenie lokalne ({host})...")
                _redis_client = Redis.from_url(f"redis://{host}:6379", decode_responses=True)
            
            await _redis_client.ping()
            logger.info("✅ [REDIS] Połączono.")
        except Exception as e:
            logger.error(f"❌ [REDIS] Błąd: {e}")
            _redis_client = None
    return _redis_client

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        try:
            logger.info("🔌 [QDRANT] Inicjalizacja...")
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small", 
                api_key=settings.openai_api_key,
                check_embedding_ctx_length=False 
            )
            
            q_url = os.environ.get("QDRANT_URL")
            q_key = os.environ.get("QDRANT_API_KEY")
            
            if not q_url or not q_key:
                raise ValueError("Brak QDRANT_URL lub QDRANT_API_KEY")

            client = QdrantClient(url=q_url, api_key=q_key, timeout=10)

            _vector_store = QdrantVectorStore(
                client=client,
                collection_name=settings.collection_name,
                embedding=embeddings,
            )
            logger.info("✅ [QDRANT] Gotowy.")
        except Exception as e:
            logger.error(f"❌ [QDRANT] Błąd: {e}")
            raise e
    return _vector_store

async def initialize_database():
    """Tylko test połączenia."""
    try:
        await get_redis()
        store = get_vector_store()
        store.similarity_search("test", k=1)
        logger.info("✅ [START] Systemy gotowe.")
    except Exception as e:
        logger.error(f"❌ [START] Błąd krytyczny: {e}")

# --- RAG LOGIC ---
async def get_rag_response(user_query: str):
    start_time = time.time()
    
    # 1. CACHE
    cache_key = ""
    redis = None
    try:
        redis = await get_redis()
        if redis:
            normalized_q = normalize_query(user_query)
            query_hash = hashlib.md5(normalized_q.encode()).hexdigest()
            cache_key = f"rag_response:{query_hash}"
            
            cached = await redis.get(cache_key)
            if cached:
                logger.info(f"⚡ [REDIS] Cache Hit!")
                return cached
    except Exception as e:
        logger.warning(f"⚠️ [REDIS] Error: {e}")

    # 2. RETRIEVAL
    context_text = ""
    try:
        vector_store = get_vector_store()
        docs = vector_store.similarity_search(user_query, k=30)
        
        unique_docs = []
        seen_titles = set()
        for doc in docs:
            # Bezpieczne pobieranie treści
            raw = doc.page_content
            content = raw.get("page_content", str(raw)) if isinstance(raw, dict) else str(raw)
            
            # Tytuł do deduplikacji
            title = content.split('\n')[0] if '\n' in content else content[:50]
            
            if title not in seen_titles:
                unique_docs.append(doc)
                seen_titles.add(title)
            if len(unique_docs) >= 8:
                break
        
        context_text = "\n\n".join([d.page_content for d in unique_docs])
    except Exception as e:
        logger.error(f"❌ [RETRIEVAL] Błąd: {e}")
        context_text = "BRAK DANYCH."

    if not context_text: context_text = "BRAK PRODUKTÓW."

    # 3. LANGFUSE & OPENAI
    system_msg = "Jesteś asystentem sklepu Estetino."
    user_msg = f"{user_query}"
    model_name = "gpt-4o-mini"
    temperature = 0
    callbacks = []
    langfuse_handler = None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        
        logger.info("3️⃣ [LANGFUSE] Inicjalizacja handlera...")
        langfuse_handler = CallbackHandler()
        # Autoryzacja testowa (opcjonalnie)
        if hasattr(langfuse_handler, 'auth_check'):
            langfuse_handler.auth_check()
            
        callbacks.append(langfuse_handler)
        
        # Klient do promptów
        lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host
        )
        
        lf_prompt = lf.get_prompt(settings.langfuse_prompt_name)
        compiled = lf_prompt.compile(
            context=context_text,
            question=user_query,
            shop_name=settings.shop_name
        )
        
        for msg in compiled:
            if msg['role'] == 'system': system_msg = msg['content']
            elif msg['role'] == 'user': user_msg = msg['content']
            
        if lf_prompt.config:
            model_name = lf_prompt.config.get("model", model_name)
            temperature = float(lf_prompt.config.get("temperature", temperature))
            
        logger.info(f"🤖 [LANGFUSE] Config OK: {model_name}, Temp={temperature}")

    except Exception as e:
        logger.warning(f"⚠️ [LANGFUSE] Błąd inicjalizacji/pobierania: {e}")

    # 4. GENEROWANIE
    try:
        model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.openai_api_key
        )
        
        response = await model.ainvoke(
            [
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg)
            ],
            config={"callbacks": callbacks}
        )
        raw_answer = response.content
    except Exception as e:
        logger.error(f"❌ [OPENAI] Błąd: {e}")
        return "Przepraszam, problem z połączeniem."

    # 5. SANITYZACJA
    clean_answer = bleach.clean(raw_answer, tags=['b', 'i', 'strong', 'em', 'a', 'br', 'p', 'ul', 'li'], attributes={'a': ['href', 'target']})

    # Cache zapisu
    try:
        if redis: await redis.setex(cache_key, 86400, clean_answer)
    except: pass
    
    # 👇 WYMUSZENIE WYSŁANIA LOGÓW (FLUSH) Z OBSŁUGĄ BŁĘDÓW
    if langfuse_handler:
        try:
            logger.info("⏳ [LANGFUSE] Wysyłanie trace'ów (flush)...")
            langfuse_handler.flush()
            logger.info("✅ [LANGFUSE] Wysłano.")
        except Exception as e:
            logger.error(f"❌ [LANGFUSE] Błąd podczas flush: {e}")

    return clean_answer