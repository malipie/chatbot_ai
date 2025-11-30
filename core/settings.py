import yaml
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    
    # Zmienne z config.yaml
    xml_url: str = ""
    shop_name: str = "Sklep"
    system_prompt: str = "Jesteś asystentem sprzedaży."

    class Config:
        env_file = ".env"
        extra = "ignore"

def load_settings():
    # 1. Ładujemy zmienne środowiskowe (.env)
    settings = Settings()
    
    # 2. Nadpisujemy plikiem YAML (jeśli istnieje)
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r", encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                settings.xml_url = yaml_config.get("xml_url", settings.xml_url)
                settings.shop_name = yaml_config.get("shop_name", settings.shop_name)
                settings.system_prompt = yaml_config.get("system_prompt", settings.system_prompt)
    
    return settings

settings = load_settings()