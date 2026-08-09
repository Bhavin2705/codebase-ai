import os
import logging
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.dim = 768

    @property
    def api_key(self) -> str:
        return os.getenv("NVIDIA_NIM_API_KEY") or getattr(settings, "NVIDIA_NIM_API_KEY", "")

    @property
    def base_url(self) -> str:
        return os.getenv("NVIDIA_NIM_BASE_URL") or getattr(settings, "NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

    @property
    def model(self) -> str:
        return os.getenv("NVIDIA_NIM_EMBED_MODEL") or getattr(settings, "NVIDIA_NIM_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.api_key or self.api_key.startswith("your_"):
            logger.error("Embedding generation failed: NVIDIA_NIM_API_KEY is missing or unconfigured")
            raise ValueError("NVIDIA_NIM_API_KEY is missing or unconfigured")
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            embedding_response = await client.embeddings.create(
                input=[text[:2000]],
                model=self.model
            )
            embedding_vector = embedding_response.data[0].embedding
            if len(embedding_vector) >= self.dim:
                return embedding_vector[:self.dim]
            return embedding_vector + [0.0] * (self.dim - len(embedding_vector))
        except Exception as error:
            logger.error("Embedding provider API call failed: %s", error, exc_info=True)
            raise RuntimeError(f"Embedding provider API call failed: {error}") from error
