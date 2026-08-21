from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Codebase Knowledge Assistant"
    VERSION: str = "1.0.0"

    DATABASE_URL: str
    GEMINI_API_KEY: str

    GEMINI_MODEL: str = "gemini-3.6-flash"

    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_CHAT_MODEL: str = "meta/llama-3.1-8b-instruct"
    NVIDIA_NIM_EMBED_MODEL: str = "nvidia/nv-embedqa-e5-v5"

    API_ACCESS_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # Optional Redis connection URL (e.g. redis://localhost:6379 or rediss://... for Upstash)
    REDIS_URL: str = ""

    # "development" | "production" — controls startup auth guard
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        extra="ignore",
        case_sensitive=True
    )


settings = Settings()

# Startup auth guard: ensure API_ACCESS_KEY is populated in production
if settings.ENVIRONMENT == "production" and not (settings.API_ACCESS_KEY or "").strip():
    raise RuntimeError(
        "API_ACCESS_KEY must be set when ENVIRONMENT=production. "
        "Set it in your Render environment variables."
    )

# Backward-compatible alias for existing imports
from app.auth import verify_api_key  # noqa: E402