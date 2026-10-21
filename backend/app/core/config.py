from pathlib import Path
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is always loaded regardless of execution working directory
for env_path in [
    Path(".env"),
    Path("backend/.env"),
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path, override=False)


class Settings(BaseSettings):
    app_name: str = "Bank Complaint AI Desk"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = os.getenv("DATABASE_URL", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    llm_model: str = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_timeout_seconds: int = 30
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
