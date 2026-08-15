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

    def _fallback_embedding(self, text: str) -> List[float]:
        import math
        raw = [math.sin(hash(text + str(i)) % 1000) for i in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [round(x / norm, 6) for x in raw]

    async def generate_embedding(self, text: str, input_type: str = "passage") -> List[float]:
        if not self.api_key or self.api_key.startswith("your_") or "your_nvidia" in self.api_key:
            return self._fallback_embedding(text)
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            kwargs = {
                "input": [text[:2000]],
                "model": self.model,
            }
            if "nvidia" in self.model.lower():
                kwargs["extra_body"] = {"input_type": input_type}
            embedding_response = await client.embeddings.create(**kwargs)
            embedding_vector = embedding_response.data[0].embedding
            if len(embedding_vector) >= self.dim:
                return embedding_vector[:self.dim]
            return embedding_vector + [0.0] * (self.dim - len(embedding_vector))
        except Exception as error:
            logger.warning("Embedding provider API call failed (%s), using deterministic fallback embedding", error)
            return self._fallback_embedding(text)
