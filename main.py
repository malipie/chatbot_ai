import os
import chainlit as cl
from fastapi import Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from core.rag_engine import initialize_database, get_rag_response, get_redis
from core.settings import settings

# --- KONFIGURACJA STARTOWA ---

@cl.on_chat_start
async def start():
    # Wiadomość powitalna
    await cl.Message(content=f"Cześć! Jestem asystentem sklepu {settings.shop_name}. W czym mogę pomóc?").send()

@cl.on_message
async def main(message: cl.Message):
    response = await get_rag_response(message.content)
    await cl.Message(content=response).send()

# --- SETUP FASTAPI (Dla Widgetu) ---
from chainlit.server import app

# 1. Inicjalizacja przy starcie serwera
@app.on_event("startup")
async def startup():
    print("🚀 Start serwera: Inicjalizacja Redis i Bazy...")
    # Inicjalizacja limitera z Redisem
    try:
        redis = await get_redis()
        await FastAPILimiter.init(redis)
        # Inicjalizacja bazy wektorowej (tylko raz)
        await initialize_database()
    except Exception as e:
        print(f"⚠️ Błąd inicjalizacji startowej: {e}")

# 2. CORS (Dostęp dla widgetu)
origins_str = os.environ.get("ALLOWED_ORIGINS", "*")
origins = origins_str.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Endpoint API (z Rate Limiterem!)
@app.post("/api/chat", dependencies=[])
async def api_chat(
    request: Request,
    # Ograniczenie: 20 zapytań na minutę z jednego IP
    limit = RateLimiter(times=20, minutes=1) 
):
    try:
        data = await request.json()
        user_message = data.get("message", "")
        
        if not user_message:
            return {"reply": "Pusta wiadomość."}
            
        response_text = await get_rag_response(user_message)
        return {"reply": response_text}
        
    except Exception as e:
        print(f"Błąd API: {e}")
        return {"reply": "Wystąpił błąd serwera."}

# 4. Serwowanie widgetu
from fastapi.staticfiles import StaticFiles
if not os.path.exists("static"): os.makedirs("static")
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass