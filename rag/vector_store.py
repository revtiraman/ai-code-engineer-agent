import chromadb
import numpy as np
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# Persistent DB so embeddings survive across runs
client = chromadb.PersistentClient(path="./vector_db")

collection = client.get_or_create_collection(
    name="repo_code"
)


class _EmbeddingModelCompat:
    """Provide a minimal sentence-transformers-like encode() API for existing code."""

    def __init__(self):
        self._embed = DefaultEmbeddingFunction()

    def encode(self, texts, batch_size=64, show_progress_bar=False):
        del batch_size
        del show_progress_bar

        if isinstance(texts, str):
            return np.array(self._embed([texts])[0])

        return np.array(self._embed(list(texts)))


embedding_model = _EmbeddingModelCompat()