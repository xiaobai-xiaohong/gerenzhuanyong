"""
Vector embedding service.
Generates 2048-dim embeddings for content.
Uses a simple TF-IDF based approach as fallback when no LLM API is configured.
"""
import json
import hashlib
import os
import sys
import numpy as np
from typing import List, Optional
from app.core.config import get_settings

settings = get_settings()


class VectorService:
    DIM: int = 2048

    def __init__(self):
        self._cache: dict[str, List[float]] = {}

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _tfidf_vector(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-embedding from text content."""
        import re
        words = re.sub(r'[^\w\s]', '', text.lower()).split()
        vec = np.zeros(self.DIM, dtype=np.float32)
        for i, word in enumerate(words[:self.DIM]):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[i % self.DIM] += (h % 1000) / 1000.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    async def embed(self, content: str) -> List[float]:
        """Get embedding for content. Uses MiniMax API first, falls back to TF-IDF."""
        key = self._hash_content(content)
        if key in self._cache:
            return self._cache[key]

        api_key = settings.model_api_key
        if api_key and api_key.strip():
            import httpx
            import logging
            # MiniMax API 走直接连接，不走代理（容器可直连外网 443）
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=10.0),
                    proxy=None,
                    trust_env=False,
                ) as client:
                    resp = await client.post(
                        "https://api.minimax.chat/v1/embeddings",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "embo-01",
                            "texts": [content[:8192]],
                            "type": "query",
                        },
                    )
                    logging.warning(f"[VectorService] MiniMax resp status={resp.status_code}")
                    if resp.status_code == 200:
                        data = resp.json()
                        vectors = data.get("vectors") or []
                        embedding = vectors[0] if vectors and isinstance(vectors[0], list) else []
                        if embedding:
                            vec = embedding[: self.DIM]
                            while len(vec) < self.DIM:
                                vec.append(0.0)
                            self._cache[key] = vec
                            logging.warning(f"[VectorService] MiniMax SUCCESS vec_dim={len(vec)}")
                            return vec
            except Exception as e:
                import traceback
                logging.warning(f"[VectorService] MiniMax EXCEPTION: {e}")

        vec = self._tfidf_vector(content)
        self._cache[key] = vec
        return vec

    async def embed_batch(self, contents: List[str]) -> List[List[float]]:
        return [await self.embed(c) for c in contents]

    def cosine_sim(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return max(0.0, dot)  # non-negative

    def vector_to_storage(self, vec: List[float]) -> str:
        return json.dumps(vec)

    def vector_from_storage(self, stored: str) -> List[float]:
        return json.loads(stored)


vector_service = VectorService()
