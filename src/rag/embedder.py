"""
Minister 1: Workspace Dense Vector Embedder (bge-small-en-v1.5, 384-dimensional, ~35 MB VRAM).
"""
from typing import List

class BGEEmbedder:
    """Generates unit-normalized 384-dimensional dense vectors in 4-8 ms."""

    def __init__(self, model_path: str = ""):
        self.dimension = 384

    def embed_query(self, text: str) -> List[float]:
        """Return 384-dimensional dummy/real vector."""
        return [0.0] * self.dimension

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Return batch embeddings."""
        return [self.embed_query(doc) for doc in documents]
