from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Codebase Knowledge Assistant"
    VERSION: str = "1.0.0"
    API_V1_STR: str = ""

    DATABASE_URL: str
    GEMINI_API_KEY: str

    GEMINI_MODEL: str = "gemini-3.5-flash"

    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_NIM_CHAT_MODEL: str = "meta/llama-3.1-70b-instruct"
    NVIDIA_NIM_EMBED_MODEL: str = "nvidia/nv-embedqa-e5-v5"

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"


settings = Settings()