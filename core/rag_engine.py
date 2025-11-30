import os
import logging
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from core.parser import smart_parse_xml
from core.settings import settings

logger = logging.getLogger(__name__)

PERSIST_DIR = "./chroma_db"

# --- LAZY LOADING BAZY ---
_vector_store = None

def get_vector_store():
    """Tworzy instancję bazy dopiero gdy jest potrzebna."""
    global _vector_store
    if _vector_store is None:
        logger.info("⚙️ Inicjalizacja ChromaDB...")
        # check_embedding_ctx_length=False -> Omija problem z pobieraniem tiktokena przy słabym DNS
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

def initialize_database():
    """Bezpieczna funkcja indeksująca."""
    try:
        store = get_vector_store()
        
        try:
            collection_data = store.get(limit=1) 
            count = len(collection_data['ids'])
        except Exception:
            count = 0
            
        if count > 0:
            logger.info(f"✅ Baza wektorowa załadowana (zawiera {count}+ elementów).")
            return 
        else:
            logger.info("📭 Baza jest pusta (mimo że folder istnieje). Rozpoczynam indeksowanie...")

    except Exception as e:
        logger.warning(f"⚠️ Problem z dostępem do bazy: {e}")

    raw_data = smart_parse_xml(settings.xml_url)
    
    if not raw_data:
        logger.warning("⚠️ Nie udało się pobrać XML lub jest pusty.")
        return

    documents = [
        Document(page_content=p['text'], metadata=p['meta']) 
        for p in raw_data
    ]
    
    store = get_vector_store()
    batch_size = 100
    
    logger.info(f"📦 Rozpoczynam dodawanie {len(documents)} produktów do bazy...")
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        store.add_documents(batch)
        if i % 500 == 0:
            logger.info(f"✅ Przetworzono {i} / {len(documents)}")
            
    logger.info("🎉 Indeksowanie zakończone sukcesem!")

def get_rag_response(user_query: str):
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
        
        print(f"📊 DEBUG: Pobranych: {len(docs)} | Unikalnych po filtracji: {len(unique_docs)}")
        
    except Exception as e:
        logger.error(f"❌ Błąd bazy Chroma: {e}")
        context_text = ""

    if not context_text:
        context_text = "BRAK PASUJĄCYCH PRODUKTÓW W BAZIE."

    print(f"🔍 Znaleziono surowych: {len(docs)}, Unikalnych: {len(unique_docs)}")

    # Domyślne wiadomości (Fallback, gdyby Langfuse padło)
    system_msg = "Jesteś asystentem sklepu Estetino. Odpowiadaj na podstawie kontekstu."
    user_msg = f"Kontekst:\n{context_text}\n\nPytanie: {user_query}"


    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler 
        
        logger.info("🔌 Łączenie z Langfuse po prompt...")
        langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host
        )
        # Pobranie promptu
        lf_prompt = langfuse_client.get_prompt("estetino-advisor")
        compiled = lf_prompt.compile(
            context=context_text,
            question=user_query,
            shop_name=settings.shop_name
        )
    
        # Przepisanie ról z Langfuse
        for msg in compiled:
            if msg['role'] == 'system':
                system_msg = msg['content']
            elif msg['role'] == 'user':
                user_msg = msg['content']
                
    except Exception as e:
        # Jeśli Langfuse rzuci błędem sieci, aplikacja NIE padnie, tylko użyje fallbacku
        logger.error(f"⚠️ Błąd Langfuse (jadę na awaryjnym prompcie): {e}")

# 3. Wysłanie do OpenAI z włączonym śledzeniem (TRACING)
    
    model = ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key)
    
    callbacks = []
    
    if Langfuse:
        try:
            from langfuse.langchain import CallbackHandler
            handler = CallbackHandler()
            callbacks.append(handler)
        except Exception as e:
            logger.warning(f"⚠️ Nie udało się podpiąć logowania do Langfuse: {e}")

    response = model.invoke(
        [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ],
        config={"callbacks": callbacks} 
    )
    
    return response.content