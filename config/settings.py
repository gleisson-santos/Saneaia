"""Configurações centralizadas da aplicação."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Carrega configurações do .env automaticamente."""

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str = ""

    # OpenRouter (LLM)
    openrouter_api_key: str
    openrouter_model: str = "deepseek/deepseek-v3.2"

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ML
    model_path: str = "ml/models/random_forest_model.joblib"
    features_path: str = "ml/models/model_features.joblib"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
