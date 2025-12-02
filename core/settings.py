import yaml
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Klucze API (Zawsze z ENV) ---
    openai_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str
    
    # --- Konfiguracja Aplikacji (ENV > YAML > Default) ---
    # Wartości domyślne są tutaj, jeśli nie ma ani ENV ani YAML
    xml_url: str = ""
    shop_name: str = "Sklep"
    system_prompt: str = "Jesteś asystentem sprzedaży."
    collection_name: str = "estetino_products"
    langfuse_prompt_name: str = "estetino-advisor"

    class Config:
        env_file = ".env"
        extra = "ignore"
        # Pydantic automatycznie czyta zmienne wielkimi literami
        # np. langfuse_prompt_name -> LANGFUSE_PROMPT_NAME

def load_settings():
    # 1. Najpierw Pydantic ładuje ENV oraz wartości domyślne
    # Jeśli w ENV jest LANGFUSE_PROMPT_NAME="test", to settings.langfuse_prompt_name = "test"
    settings = Settings()
    
    # 2. Doczytujemy YAML jako "Fallback" (niższy priorytet)
    if os.path.exists("config.yaml"):
        try:
            with open("config.yaml", "r", encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                
            if yaml_config:
                # Pomocnicza funkcja: Weź z YAML tylko jeśli NIE MA w ENV
                # (czyli ENV ma pierwszeństwo, potem YAML, na końcu default z klasy)
                
                def apply_yaml_if_missing_env(field_name, env_var_name):
                    # Jeśli zmienna środowiskowa NIE istnieje, nadpisz wartością z YAML (jeśli jest w YAML)
                    if env_var_name not in os.environ:
                        yaml_val = yaml_config.get(field_name)
                        if yaml_val:
                            setattr(settings, field_name, yaml_val)

                # --- Lista pól do sprawdzenia ---
                apply_yaml_if_missing_env("xml_url", "XML_URL")
                apply_yaml_if_missing_env("shop_name", "SHOP_NAME")
                apply_yaml_if_missing_env("system_prompt", "SYSTEM_PROMPT")
                apply_yaml_if_missing_env("collection_name", "COLLECTION_NAME")
                apply_yaml_if_missing_env("langfuse_prompt_name", "LANGFUSE_PROMPT_NAME")
                
        except Exception as e:
            print(f"⚠️ Ostrzeżenie: Problem z plikiem config.yaml: {e}")
    
    return settings

settings = load_settings()

# import yaml
# import os
# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     # Klucze API (z .env)
#     openai_api_key: str
#     langfuse_public_key: str
#     langfuse_secret_key: str
#     langfuse_host: str
    
#     # Zmienne z config.yaml (musisz je tu zadeklarować!)
#     xml_url: str = ""
#     shop_name: str = "Sklep"
#     system_prompt: str = "Jesteś asystentem sprzedaży."
#     # 👇 NOWE POLE:
#     collection_name: str = "estetino_products" 
#     langfuse_prompt_name: str = "estetino-advisor"

#     class Config:
#         env_file = ".env"
#         extra = "ignore"

# def load_settings():
#     # 1. Ładujemy zmienne środowiskowe (.env)
#     settings = Settings()
    
#     # 2. Nadpisujemy plikiem YAML (jeśli istnieje)
#     if os.path.exists("config.yaml"):
#         with open("config.yaml", "r", encoding='utf-8') as f:
#             yaml_config = yaml.safe_load(f)
#             if yaml_config:
#                 # Przepisujemy wartości z YAML do obiektu settings
#                 settings.xml_url = yaml_config.get("xml_url", settings.xml_url)
#                 settings.shop_name = yaml_config.get("shop_name", settings.shop_name)
#                 settings.system_prompt = yaml_config.get("system_prompt", settings.system_prompt)
#                 settings.collection_name = yaml_config.get("collection_name", settings.collection_name)
#                 settings.langfuse_prompt_name = yaml_config.get("langfuse_prompt_name", settings.langfuse_prompt_name)
    
#     return settings

# settings = load_settings()