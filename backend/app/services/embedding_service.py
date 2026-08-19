import os
import logging
import asyncio
from typing import List
import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


MAX_EMBEDDING_CHARS = 750


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
                "input": [text[:MAX_EMBEDDING_CHARS]],
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

    async def generate_embeddings_batch(
        self, texts: List[str], input_type: str = "passage", batch_size: int = 150
    ) -> List[List[float]]:
        if not texts:
            return []

        api_key = self.api_key
        if not api_key or api_key.startswith("your_") or "your_nvidia" in api_key:
            raise RuntimeError("NVIDIA NIM embedding provider is not configured")

        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        chunks = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        results: List[List[float]] = [None] * len(texts)  # type: ignore

        sem = asyncio.Semaphore(15)
        limits = httpx.Limits(max_keepalive_connections=35, max_connections=45)

        async with httpx.AsyncClient(timeout=20.0, limits=limits) as client:
            async def process_chunk(start_idx: int, chunk_texts: List[str]):
                payload = {
                    "input": [t[:MAX_EMBEDDING_CHARS] if t else "code" for t in chunk_texts],
                    "model": self.model,
                }
                if "nvidia" in self.model.lower():
                    payload["input_type"] = input_type

                try:
                    async with sem:
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            for offset, item in enumerate(data.get("data", [])):
                                vec = item["embedding"]
                                if len(vec) >= self.dim:
                                    vec = vec[: self.dim]
                                else:
                                    vec = vec + [0.0] * (self.dim - len(vec))
                                results[start_idx + offset] = vec
                        else:
                            logger.warning(
                                "Batch embedding request returned HTTP %s: %s",
                                resp.status_code,
                                resp.text,
                            )
                except Exception as e:
                    logger.warning("Batch embedding request failed: %s", e)

            tasks = [
                process_chunk(i * batch_size, chunk)
                for i, chunk in enumerate(chunks)
            ]
            await asyncio.gather(*tasks)

        if any(result is None for result in results):
            failed_count = sum(result is None for result in results)
            raise RuntimeError(
                f"Embedding generation failed for {failed_count} items"
            )

        return results
