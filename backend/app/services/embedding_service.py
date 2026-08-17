import os
import logging
from typing import List
import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.dim = 768

    @property
    def api_key(self) -> str:
        return os.getenv("NVIDIA_NIM_API_KEY") or getattr(
            settings, "NVIDIA_NIM_API_KEY", ""
        )

    @property
    def base_url(self) -> str:
        return os.getenv("NVIDIA_NIM_BASE_URL") or getattr(
            settings,
            "NVIDIA_NIM_BASE_URL",
            "https://integrate.api.nvidia.com/v1",
        )

    @property
    def model(self) -> str:
        return os.getenv("NVIDIA_NIM_EMBED_MODEL") or getattr(
            settings,
            "NVIDIA_NIM_EMBED_MODEL",
            "nvidia/nv-embedqa-e5-v5",
        )

    async def generate_embedding(
        self, text: str, input_type: str = "passage"
    ) -> List[float]:
        api_key = self.api_key
        if not api_key or api_key.startswith("your_") or "your_nvidia" in api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Vector embedding provider is unconfigured or unavailable.",
            )

        try:
            url = f"{self.base_url.rstrip('/')}/embeddings"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "input": [text[:2000]],
                "model": self.model,
            }
            if "nvidia" in self.model.lower():
                payload["input_type"] = input_type

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Vector embedding provider returned HTTP {resp.status_code}: {resp.text}",
                )

            data = resp.json()
            embedding_vector = data["data"][0]["embedding"]

            if len(embedding_vector) >= self.dim:
                return embedding_vector[:self.dim]
            return embedding_vector + [0.0] * (self.dim - len(embedding_vector))

        except HTTPException:
            raise
        except Exception as error:
            logger.error("Embedding generation failed: %s", error)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Vector embedding provider unavailable: {error}",
            )
