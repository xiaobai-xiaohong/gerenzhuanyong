"""
Vector embedding service.
Generates 2048-dim embeddings for content.
Supports: MiniMax, DeepSeek, TF-IDF fallback.
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

    async def _embed_minimax(self, content: str) -> Optional[List[float]]:
        """Call MiniMax embedding API."""
        api_key = settings.model_api_key
        if not api_key or not api_key.strip():
            return None
        import httpx
        import logging
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
                        logging.warning(f"[VectorService] MiniMax SUCCESS vec_dim={len(vec)}")
                        return vec
        except Exception as e:
            logging.warning(f"[VectorService] MiniMax EXCEPTION: {e}")
        return None

    async def _embed_deepseek(self, content: str) -> Optional[List[float]]:
        """Call DeepSeek embedding API (OpenAI-compatible)."""
        api_key = settings.deepseek_api_key
        if not api_key or not api_key.strip():
            return None
        import httpx
        import logging
        base_url = settings.deepseek_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                proxy=None,
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{base_url}/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-embedding",
                        "input": content[:8192],
                    },
                )
                logging.warning(f"[VectorService] DeepSeek resp status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data") or []
                    embedding = items[0].get("embedding") if items else []
                    if embedding:
                        vec = embedding[: self.DIM]
                        while len(vec) < self.DIM:
                            vec.append(0.0)
                        logging.warning(f"[VectorService] DeepSeek SUCCESS vec_dim={len(vec)}")
                        return vec
        except Exception as e:
            logging.warning(f"[VectorService] DeepSeek EXCEPTION: {e}")
        return None

    async def _embed_siliconflow(self, content: str) -> Optional[List[float]]:
        """Call Silicon Flow embedding API (OpenAI-compatible)."""
        api_key = settings.siliconflow_api_key
        if not api_key or not api_key.strip():
            return None
        import httpx
        import logging
        base_url = settings.siliconflow_base_url.rstrip("/")
        model = settings.siliconflow_model
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                proxy=None,
                trust_env=False,
            ) as client:
                resp = await client.post(
                    f"{base_url}/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "input": content[:8192],
                    },
                )
                logging.warning(f"[VectorService] SiliconFlow resp status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data") or []
                    embedding = items[0].get("embedding") if items else []
                    if embedding:
                        vec = embedding[: self.DIM]
                        while len(vec) < self.DIM:
                            vec.append(0.0)
                        logging.warning(f"[VectorService] SiliconFlow SUCCESS vec_dim={len(vec)}")
                        return vec
        except Exception as e:
            logging.warning(f"[VectorService] SiliconFlow EXCEPTION: {e}")
        return None

    async def embed(self, content: str) -> List[float]:
        """Get embedding for content. Provider priority: config -> fallback TF-IDF."""
        key = self._hash_content(content)
        if key in self._cache:
            return self._cache[key]

        provider = settings.model_provider.lower()
        vec = None

        if provider == "siliconflow":
            vec = await self._embed_siliconflow(content)
        elif provider == "deepseek":
            vec = await self._embed_deepseek(content)
        elif provider == "minimax":
            vec = await self._embed_minimax(content)
        elif provider == "tfidf":
            vec = None  # skip API, go straight to TF-IDF
        else:
            # auto: try siliconflow -> minimax -> deepseek
            vec = await self._embed_siliconflow(content)
            if not vec:
                vec = await self._embed_minimax(content)
            if not vec:
                vec = await self._embed_deepseek(content)

        if not vec:
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
