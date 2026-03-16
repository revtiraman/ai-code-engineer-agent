import os

import numpy as np
from rag.vector_store import collection, embedding_model
from utils.logger import get_logger

logger = get_logger("retriever")


def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def retriever_node(state):

    query = state["user_prompt"]
    repo_id = state.get("repo_id")

    logger.info("Searching repository for: %s", query)

    query_embedding = embedding_model.encode(query).tolist()

    # Fetch 30 candidates so reranking has a good pool
    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": 30,
        "include": ["documents", "metadatas", "embeddings"],
    }
    if repo_id:
        query_kwargs["where"] = {"repo_id": repo_id}

    results = collection.query(**query_kwargs)

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    embeddings = (results.get("embeddings") or [[]])[0]

    # --------------------------------------------------
    # RERANKING: exact cosine similarity against query
    # --------------------------------------------------
    scored = []

    for doc, meta, emb in zip(documents, metadatas, embeddings):

        if not isinstance(meta, dict):
            continue

        file_path = meta.get("file", "unknown")
        code_type = meta.get("type", "unknown")
        name      = meta.get("name", "unknown")

        if "docs" in file_path or "examples" in file_path:
            continue

        # Ignore stale vector entries that no longer exist on disk.
        if not os.path.exists(file_path):
            continue

        score = cosine_similarity(query_embedding, emb)

        scored.append({
            "file":  file_path,
            "type":  code_type,
            "name":  name,
            "code":  doc,
            "score": score
        })

    # Sort descending by similarity score
    scored.sort(key=lambda x: x["score"], reverse=True)
    function_scored = [b for b in scored if b.get("type") == "function"]
    top_blocks = function_scored[:10] if function_scored else scored[:10]

    relevant_files   = []
    retrieved_blocks = []

    logger.info("Top retrieved blocks after reranking:")

    for block in top_blocks:

        logger.info(
            "  [%.4f]  %s  ::  %s  (%s)",
            block["score"], block["file"], block["name"], block["type"]
        )

        retrieved_blocks.append({
            "file":  block["file"],
            "type":  block["type"],
            "name":  block["name"],
            "code":  block["code"],
            "score": block["score"]
        })

        if block["file"] not in relevant_files:
            relevant_files.append(block["file"])

        if len(relevant_files) >= 5:
            break

    state["relevant_files"]   = relevant_files
    state["retrieved_blocks"] = retrieved_blocks

    if not retrieved_blocks:
        logger.warning("No retrievable live code blocks found for query")

    logger.info("Relevant files: %s", relevant_files)

    return state
