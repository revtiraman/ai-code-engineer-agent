import hashlib
import numpy as np
try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
except Exception:
    chromadb = None
    DefaultEmbeddingFunction = None


class _InMemoryCollection:
    def __init__(self):
        self._records = []

    def count(self):
        return len(self._records)

    def delete(self, where=None):
        if not where:
            self._records = []
            return

        repo_id = where.get("repo_id")
        if repo_id is None:
            self._records = []
            return

        self._records = [r for r in self._records if (r.get("metadata") or {}).get("repo_id") != repo_id]

    def add(self, ids, documents, embeddings, metadatas):
        for i, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
            self._records.append({
                "id": i,
                "document": doc,
                "embedding": np.array(emb, dtype=float),
                "metadata": meta,
            })

    def query(self, query_embeddings, n_results=10, include=None, where=None):
        include = include or []
        query_vec = np.array(query_embeddings[0], dtype=float)

        candidates = self._records
        if where and "repo_id" in where:
            repo_id = where["repo_id"]
            candidates = [r for r in candidates if (r.get("metadata") or {}).get("repo_id") == repo_id]

        scored = []
        for r in candidates:
            emb = r["embedding"]
            sim = float(np.dot(query_vec, emb) / (np.linalg.norm(query_vec) * np.linalg.norm(emb) + 1e-10))
            scored.append((sim, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [r for _, r in scored[:n_results]]

        return {
            "documents": [[r["document"] for r in top]] if "documents" in include else [[]],
            "metadatas": [[r["metadata"] for r in top]] if "metadatas" in include else [[]],
            "embeddings": [[r["embedding"].tolist() for r in top]] if "embeddings" in include else [[]],
        }


if chromadb is not None:
    # Persistent DB so embeddings survive across runs
    client = chromadb.PersistentClient(path="./vector_db")
    collection = client.get_or_create_collection(name="repo_code")
else:
    collection = _InMemoryCollection()


class _EmbeddingModelCompat:
    """Provide a minimal sentence-transformers-like encode() API for existing code."""

    def __init__(self):
        self._embed = DefaultEmbeddingFunction() if DefaultEmbeddingFunction else None

    @staticmethod
    def _hash_embed(text: str, size: int = 256):
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        arr = np.frombuffer((digest * ((size // len(digest)) + 1))[:size], dtype=np.uint8).astype(float)
        # Normalize into unit-ish vector space
        arr = (arr - 127.5) / 127.5
        return arr

    def encode(self, texts, batch_size=64, show_progress_bar=False):
        del batch_size
        del show_progress_bar

        if self._embed is not None:
            if isinstance(texts, str):
                return np.array(self._embed([texts])[0])

            return np.array(self._embed(list(texts)))

        if isinstance(texts, str):
            return self._hash_embed(texts)

        return np.array([self._hash_embed(t) for t in list(texts)])


embedding_model = _EmbeddingModelCompat()