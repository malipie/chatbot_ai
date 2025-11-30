import os
import chainlit as cl
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from core.rag_engine import initialize_database, get_rag_response
from core.settings import settings

# --- KONFIGURACJA STARTOWA ---
@cl.on_chat_start
async def start():
    print("🚀 Start sesji czatu...")
    # Inicjalizacja bazy przy starcie (tylko raz)
    initialize_database()
    
    # Wiadomość powitalna
    await cl.Message(content=f"Cześć! Jestem asystentem sklepu {settings.shop_name}. W czym mogę pomóc?").send()

# --- OBSŁUGA UI CHAINLIT ---
@cl.on_message
async def main(message: cl.Message):
    response = get_rag_response(message.content)
    await cl.Message(content=response).send()

# --- API DLA WIDGETU JS ---
from chainlit.server import app

# Dodajemy Middleware TYLKO jeśli jeszcze go nie ma (zapobiega błędom przy reloadzie)
# Sprawdzamy czy CORS już jest w aplikacji
middleware_exists = any(m.cls == CORSMiddleware for m in app.user_middleware)

if not middleware_exists:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.post("/api/chat")
async def api_chat(request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    
    if not user_message:
        return {"reply": "Pusta wiadomość."}
        
    response_text = get_rag_response(user_message)
    return {"reply": response_text}

# Serwowanie pliku widget.js
from fastapi.staticfiles import StaticFiles
import os
if not os.path.exists("static"): os.makedirs("static")
# Montowanie static files tylko raz
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass # Ignorujemy błąd jeśli już zamontowane