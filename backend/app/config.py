from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Codebase Knowledge Assistant"
    VERSION: str = "1.0.0"

    DATABASE_URL: str
    GEMINI_API_KEY: str

    GEMINI_MODEL: str = "gemini-3.5-flash"

    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_CHAT_MODEL: str = "meta/llama-3.1-70b-instruct"
    NVIDIA_NIM_EMBED_MODEL: str = "nvidia/nv-embedqa-e5-v5"

    API_ACCESS_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # "development" | "production" — controls startup auth guard
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()

# ── Startup auth guard ────────────────────────────────────────────────────────
if settings.ENVIRONMENT == "production" and not (settings.API_ACCESS_KEY or "").strip():
    raise RuntimeError(
        "API_ACCESS_KEY must be set when ENVIRONMENT=production. "
        "Set it in your Render environment variables."
    )
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import Header, HTTPException, status

async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    expected = (settings.API_ACCESS_KEY or "").strip()
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )