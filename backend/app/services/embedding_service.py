import os
from typing import List
from app.config import settings

class EmbeddingService:
    def __init__(self):
        self.vector_dim = 768

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
            return [0.0] * self.vector_dim
        
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.embeddings.create(
                input=[text[:2000]],
                model=self.model
            )
            embedding_vector = response.data[0].embedding
            if len(embedding_vector) >= self.vector_dim:
                return embedding_vector[:self.vector_dim]
            else:
                return embedding_vector + [0.0] * (self.vector_dim - len(embedding_vector))
        except Exception as error:
            print(f"Error generating embedding via NVIDIA NIM: {error}")
            return [0.0] * self.vector_dim

