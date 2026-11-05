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
    app_name: str = os.getenv("APP_NAME", "Bank Complaint AI Desk")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "https://bank-complaints-ai-desk.vercel.app")
    cors_origins: str = os.getenv("CORS_ORIGINS", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    llm_model: str = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    regulation_similarity_threshold: float = float(os.getenv("REGULATION_SIMILARITY_THRESHOLD", "0.40"))

    # Email & SMTP Configurations
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")

    # Alternative Email Providers
    brevo_api_key: str = os.getenv("BREVO_API_KEY", "")
    brevo_sender_email: str = os.getenv("BREVO_SENDER_EMAIL", "")
    brevo_sender_name: str = os.getenv("BREVO_SENDER_NAME", "Bank Complaint AI Desk")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from: str = os.getenv("RESEND_FROM", "")
    maileroo_api_key: str = os.getenv("MAILEROO_API_KEY", "")
    maileroo_from: str = os.getenv("MAILEROO_FROM", "")
    vercel_url: str = os.getenv("VERCEL_URL", "")
    turnstile_secret_key: str = os.getenv("TURNSTILE_SECRET_KEY", "")

    stripe_secret_key : str=os.getenv("STRIPE_SECRET_KEY","")
    stripe_publishable_key:str=os.getenv("STRIPE_PUBLISHABLE_KEY","")
    stripe_price_id:str=os.getenv("STRIPE_PRICE_ID","")
    stripe_webhook_secret:str=os.getenv("STRIPE_WEBHOOK_SECRET","")


    environment: str = os.getenv("ENVIRONMENT", "production")

    @property
    def allowed_origins(self) -> list[str]:
        raw_list = []
        if self.cors_origins:
            raw_list.extend([o.strip() for o in self.cors_origins.split(",") if o.strip()])
        if self.frontend_origin:
            raw_list.append(self.frontend_origin.strip().rstrip("/"))
        raw_list.extend([
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
            "https://bank-complaints-ai-desk.vercel.app",
        ])
        return list(dict.fromkeys(raw_list))

    def get_safe_frontend_origin(self, request=None, prefer_public: bool = False) -> str:
        """Returns a verified, whitelisted frontend origin. Never trusts arbitrary Origin/Host headers.
        If prefer_public is True (e.g. for outgoing emails), converts localhost origins to the
        public production domain so links can be clicked from external email clients and mobile devices.
        """
        public_url = "https://bank-complaints-ai-desk.vercel.app"
        if request:
            req_origin = (request.headers.get("origin") or "").strip().rstrip("/")
            if req_origin in self.allowed_origins:
                if prefer_public and ("localhost" in req_origin or "127.0.0.1" in req_origin):
                    return public_url
                return req_origin

        cand = (self.frontend_origin or public_url).rstrip("/")
        if prefer_public and ("localhost" in cand or "127.0.0.1" in cand):
            return public_url
        return cand

    model_config = SettingsConfigDict(extra="ignore")



settings = Settings()
