# import ast
# from concurrent.futures import ThreadPoolExecutor

# from rag.vector_store import collection, embedding_model


# def extract_code_structures(code, file_path):
#     """
#     Extract classes and functions using Python AST
#     """

#     entries = []

#     try:
#         tree = ast.parse(code)

#         lines = code.splitlines()

#         for node in ast.walk(tree):

#             if isinstance(node, ast.FunctionDef):

#                 start = node.lineno
#                 end = node.end_lineno

#                 func_code = "\n".join(lines[start-1:end])

#                 entries.append({
#                     "text": func_code,
#                     "metadata": {
#                         "file": file_path,
#                         "type": "function",
#                         "name": node.name
#                     }
#                 })

#             elif isinstance(node, ast.ClassDef):

#                 start = node.lineno
#                 end = node.end_lineno

#                 class_code = "\n".join(lines[start-1:end])

#                 entries.append({
#                     "text": class_code,
#                     "metadata": {
#                         "file": file_path,
#                         "type": "class",
#                         "name": node.name
#                     }
#                 })

#     except:
#         pass

#     return entries


# def fallback_chunking(code, file_path, chunk_size=500, overlap=100):
#     """
#     Fallback if AST parsing fails
#     """

#     chunks = []

#     start = 0

#     while start < len(code):

#         end = start + chunk_size

#         chunk = code[start:end]

#         chunks.append({
#             "text": chunk,
#             "metadata": {
#                 "file": file_path,
#                 "type": "chunk"
#             }
#         })

#         start += chunk_size - overlap

#     return chunks


# def read_file(file_path):

#     try:
#         with open(file_path, "r", encoding="utf-8") as f:
#             return file_path, f.read()
#     except:
#         return file_path, None


# def repo_indexer_node(state):

#     if state.get("repo_indexed"):

#         print("Repository already indexed")

#         return state

#     files = state["files"]

#     print("Reading repository files...")

#     all_entries = []

#     with ThreadPoolExecutor() as executor:

#         results = list(executor.map(read_file, files))

#     for file_path, code in results:

#         if code is None:
#             continue

#         structures = extract_code_structures(code, file_path)

#         if len(structures) == 0:

#             structures = fallback_chunking(code, file_path)

#         all_entries.extend(structures)

#     texts = [entry["text"] for entry in all_entries]

#     metadatas = [entry["metadata"] for entry in all_entries]

#     print(f"Total indexed code blocks: {len(texts)}")

#     print("Creating embeddings...")

#     embeddings = embedding_model.encode(
#         texts,
#         batch_size=64,
#         show_progress_bar=True
#     )

#     ids = [str(i) for i in range(len(texts))]

#     collection.add(
#         ids=ids,
#         documents=texts,
#         embeddings=embeddings,
#         metadatas=metadatas
#     )

#     state["repo_indexed"] = True

#     print("Repository indexing completed")

#     return state
import ast
import os
from concurrent.futures import ThreadPoolExecutor

from rag.vector_store import collection, embedding_model


MAX_CODE_SIZE = 2000
FORCE_REINDEX = os.getenv("FORCE_REINDEX", "1") == "1"


def extract_code_structures(code, file_path, repo_id):

    entries = []

    try:

        tree = ast.parse(code)

        lines = code.splitlines()

        for node in ast.walk(tree):

            if isinstance(node, ast.FunctionDef):

                start = node.lineno
                end = node.end_lineno

                func_code = "\n".join(lines[start - 1:end])

                func_code = func_code[:MAX_CODE_SIZE]

                entries.append({
                    "text": func_code,
                    "metadata": {
                        "file": file_path,
                        "repo_id": repo_id,
                        "type": "function",
                        "name": node.name
                    }
                })

            elif isinstance(node, ast.ClassDef):

                start = node.lineno
                end = node.end_lineno

                class_code = "\n".join(lines[start - 1:end])

                class_code = class_code[:MAX_CODE_SIZE]

                entries.append({
                    "text": class_code,
                    "metadata": {
                        "file": file_path,
                        "repo_id": repo_id,
                        "type": "class",
                        "name": node.name
                    }
                })

    except Exception:
        pass

    return entries


def fallback_chunking(code, file_path, repo_id, chunk_size=500, overlap=100):

    chunks = []

    start = 0

    while start < len(code):

        end = start + chunk_size

        chunk = code[start:end]

        chunks.append({
            "text": chunk,
            "metadata": {
                "file": file_path,
                "repo_id": repo_id,
                "type": "chunk"
            }
        })

        start += chunk_size - overlap

    return chunks


def read_file(file_path):

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return file_path, f.read()
    except Exception:
        return file_path, None


def repo_indexer_node(state):
    repo_id = state.get("repo_id", "default_repo")
    existing_count = collection.count()

    print(f"Indexing start for repo_id={repo_id}")

    if existing_count > 0 and not FORCE_REINDEX:
        print("Vector DB already contains data. Skipping indexing.")
        state["repo_indexed"] = True
        return state

    if existing_count > 0 and FORCE_REINDEX:
        try:
            collection.delete(where={"repo_id": repo_id})
            print(f"Cleared existing vector entries for repo: {repo_id}")
        except Exception:
            # Non-fatal: unique IDs still avoid collisions if delete fails.
            print(f"Warning: could not clear vectors for repo: {repo_id}")

    files = state["files"]

    print("Reading repository files...")

    all_entries = []

    with ThreadPoolExecutor(max_workers=8) as executor:

        results = list(executor.map(read_file, files))

    for file_path, code in results:

        if code is None:
            continue

        structures = extract_code_structures(code, file_path, repo_id)

        if len(structures) == 0:

            structures = fallback_chunking(code, file_path, repo_id)

        all_entries.extend(structures)

    texts = [entry["text"] for entry in all_entries]

    metadatas = [entry["metadata"] for entry in all_entries]

    print(f"Total indexed code blocks: {len(texts)}")

    if not texts:
        print("No indexable code blocks found.")
        state["repo_indexed"] = True
        return state

    print("Creating embeddings...")

    embeddings = embedding_model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True
    )

    ids = [f"{repo_id}:{i}" for i in range(len(texts))]

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas
    )

    state["repo_indexed"] = True
    state["indexed_blocks"] = len(texts)

    print(f"Indexed {len(texts)} blocks for repo_id={repo_id}")

    print("Repository indexing completed")

    return state