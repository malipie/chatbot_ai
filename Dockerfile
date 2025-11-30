FROM python:3.11-slim

WORKDIR /app

# Instalacja zależności systemowych (potrzebne czasem do kompilacji bibliotek)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Kopiowanie zależności i instalacja
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu aplikacji
COPY . .

# Wystawienie portu
EXPOSE 8000

# Komenda uruchamiająca (Chainlit)
CMD ["chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]