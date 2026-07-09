"""
knowledge_base.py

RAG retrieval tool for the Farm Manager's general layer-poultry
operations knowledge. This is DELIBERATELY SCOPED — it only covers
day-to-day layer farm operations (10 categories: fundamentals,
flock lifecycle, housing, feeding, egg production, records,
performance analysis, operations, general health AWARENESS, and
biosecurity). It does NOT contain deep veterinary/diagnostic
content — that's reserved for a future, separate Health Advisory
Agent (accessed via A2A), matching the boundary already encoded
in each category's own "Escalation" section.

Backed by:
  - A FAISS IndexFlatIP index (10 vectors, category-based chunks)
  - BAAI/bge-base-en-v1.5 embeddings (768-dim, normalized)
  - A metadata pickle holding each category's full text content

The index/metadata/model are loaded once (module-level, lazy) and
reused across calls — NOT reloaded on every query.
"""

import pickle
import numpy as np
import faiss

INDEX_PATH = "agroscan/knowledge_base/farm_manager_index.faiss"
METADATA_PATH = "agroscan/knowledge_base/farm_manager_metadata.pkl"
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
TOP_K = 3
MIN_RELEVANCE_SCORE = 0.45  # cosine similarity threshold — tune based on real query testing

# Lazy-loaded singletons — populated on first use, not at import time.
_index = None
_metadata = None
_embedding_model = None


def _load_resources():
    """Loads the FAISS index, metadata, and embedding model exactly
    once, caching them at module level for reuse across queries."""
    global _index, _metadata, _embedding_model

    if _index is None:
        _index = faiss.read_index(INDEX_PATH)

    if _metadata is None:
        with open(METADATA_PATH, "rb") as f:
            _metadata = pickle.load(f)

    if _embedding_model is None:
        # Imported here, not at module top, so environments that never
        # call this tool don't pay the torch/transformers import cost.
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def search_farm_knowledge_base(query: str):
    """
    Search AgroScan's general layer-poultry farm operations
    knowledge base for information relevant to the farmer's
    question.

    IMPORTANT: This tool covers general layer-farm OPERATIONS
    knowledge only — flock lifecycle, housing, feeding, egg
    production, records, performance, day-to-day operations,
    GENERAL health awareness (not diagnosis), and biosecurity.
    It does NOT contain deep veterinary/disease-diagnostic
    knowledge.

    Always call this tool for general farming knowledge questions
    rather than answering from memory. If this tool returns no
    relevant result, say so honestly rather than answering from
    general knowledge.

    Args:
        query: The farmer's question, in natural language.

    Returns:
        A dict with the top matching categories, each including
        the category title and its full content, so the agent can
        answer using only this retrieved, scoped information.
    """
    _load_resources()

    query_embedding = _embedding_model.encode([query], normalize_embeddings=True)
    query_embedding = np.array(query_embedding, dtype="float32")

    scores, indices = _index.search(query_embedding, TOP_K)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_metadata):
            continue
        if score < MIN_RELEVANCE_SCORE:
            continue  # too weak a match — exclude rather than let the model blend it in
        category = _metadata[idx]
        results.append({
            "category": category["title"],
            "relevance_score": float(score),
            "content": category["content"],
        })

    if not results:
        return {
            "found": False,
            "instruction_to_agent": (
                "No sufficiently relevant information exists in the knowledge base "
                "for this query. You must tell the farmer you don't have specific "
                "guidance on this topic. Do NOT answer this question using your own "
                "general knowledge, even partially, and do NOT mention search "
                "results, tools, or retrieval — just state plainly that you don't "
                "have information on this topic in your knowledge base."
            ),
        }

    return {
        "found": True,
        "results": results,
        "instruction_to_agent": (
            "Answer using ONLY the content in these results. Do not add details, "
            "figures, or advice beyond what is stated here."
        ),
    }
