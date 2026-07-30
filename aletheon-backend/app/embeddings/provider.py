import abc
import math
import numpy as np
from typing import List
import httpx
from app.config import settings


class EmbeddingProvider(abc.ABC):

    @abc.abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings into float vector representations."""
        pass

    @abc.abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query text."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based embedding provider for unit tests and local execution without API keys."""

    def __init__(self, dim: int = 1536):
        self.dim = dim

    def _hash_text(self, text: str) -> List[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        words = text.lower().split()
        for idx, word in enumerate(words):
            val = sum(ord(c) for c in word)
            slot = val % self.dim
            vec[slot] += (1.0 / (idx + 1)) + (val % 10) * 0.1

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_text(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        return self._hash_text(query)


class OpenAIEmbeddingProvider(EmbeddingProvider):

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key or self.api_key == "mock-key":
            return await MockEmbeddingProvider().embed_texts(texts)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    async def embed_query(self, query: str) -> List[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0]


class VoyageEmbeddingProvider(EmbeddingProvider):

    def __init__(self, api_key: str, model: str = "voyage-large-2"):
        self.api_key = api_key
        self.model = model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key or self.api_key == "mock-key":
            return await MockEmbeddingProvider().embed_texts(texts)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    async def embed_query(self, query: str) -> List[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0]


def get_embedding_provider() -> EmbeddingProvider:
    provider_name = settings.EMBEDDING_PROVIDER.lower()
    if provider_name == "openai":
        return OpenAIEmbeddingProvider(settings.EMBEDDING_API_KEY, settings.EMBEDDING_MODEL)
    elif provider_name == "voyage":
        return VoyageEmbeddingProvider(settings.EMBEDDING_API_KEY, settings.EMBEDDING_MODEL)
    else:
        return MockEmbeddingProvider()
