import os
import hashlib
from typing import List
from app.config import settings

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

    def _fallback_vector(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        v = [(b / 255.0) - 0.5 for b in h]
        repeats = (self.dim // len(v)) + 1
        vec = (v * repeats)[:self.dim]
        return vec

    async def generate_embedding(self, text: str) -> List[float]:
        if not self.api_key or self.api_key.startswith("your_"):
            return self._fallback_vector(text)
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            res = await client.embeddings.create(
                input=[text[:2000]],
                model=self.model
            )
            emb = res.data[0].embedding
            if len(emb) >= self.dim:
                return emb[:self.dim]
            return emb + [0.0] * (self.dim - len(emb))
        except Exception:
            return self._fallback_vector(text)
