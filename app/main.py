import os
import logging
from typing import Optional, List, Dict, Any

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="[%(asctime)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(url, poolclass=NullPool, future=True)


# Try to reuse provider from scripts.embed; fallback to local implementation
def vector_literal(vec: list[float]) -> str:
    return "[" + ", ".join(f"{x:.8f}" for x in vec) + "]"


class SimpleLocalEmbed:
    def __init__(self, dim: int = 1536):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import math, random
        out = []
        for t in texts:
            rnd = random.Random(abs(hash(t)))
            vec = [rnd.uniform(-1.0, 1.0) for _ in range(self.dim)]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vec = [x / norm for x in vec]
            out.append(vec)
        return out


def get_embedding_provider():
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    if provider == "openai":
        try:
            from scripts.embed import OpenAIEmbedding  # type: ignore
            return OpenAIEmbedding(model=model)
        except Exception as e:
            logger.warning(f"Falling back to local embeddings: {e}")
            return SimpleLocalEmbed()
    else:
        try:
            from scripts.embed import LocalEmbedding  # type: ignore
            return LocalEmbedding(model=model)
        except Exception:
            return SimpleLocalEmbed()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    ministry: Optional[str] = None


app = FastAPI(title="Gov Minutes RAG API")
engine = get_engine()
provider = get_embedding_provider()


@app.get("/healthz")
def healthz():
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
def search(req: SearchRequest) -> List[Dict[str, Any]]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    has_top_k = "top_k" in req.__fields_set__
    requested_top_k = req.top_k if has_top_k else 5
    final_top_k = requested_top_k if requested_top_k and requested_top_k > 0 else 5
    final_top_k = max(1, min(20, final_top_k))
    fetch_limit = final_top_k * 5 if has_top_k else 5 * 5
    fetch_limit = max(fetch_limit, final_top_k)

    # Embed query
    vec = provider.embed([req.query])[0]
    vec_lit = vector_literal(vec)

    sql = text(
        """
        SELECT m.url, m.council_name, m.date, c.chunk_text,
               1 - (c.embedding <=> CAST(:query_vec AS vector)) AS score
        FROM meeting_chunks c
        JOIN meeting_metadata m ON c.doc_id = m.doc_id
        WHERE (:ministry IS NULL OR m.ministry = :ministry)
        ORDER BY c.embedding <=> CAST(:query_vec AS vector)
        LIMIT :limit
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "query_vec": vec_lit,
                "ministry": req.ministry,
                "limit": fetch_limit,
            },
        ).fetchall()

    grouped_results: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        url = r[0]
        score_val = float(r[4]) if r[4] is not None else 0.0
        if url not in grouped_results:
            grouped_results[url] = {
                "url": url,
                "council_name": r[1],
                "date": r[2].isoformat() if r[2] else None,
                "_scores": [score_val],
                "_chunks": [r[3]],
            }
        else:
            grouped_results[url]["_scores"].append(score_val)
            grouped_results[url]["_chunks"].append(r[3])

    unique_results: List[Dict[str, Any]] = []
    for data in grouped_results.values():
        scores = data.pop("_scores", [])
        chunks = data.pop("_chunks", [])
        match_count = len(scores)
        avg_score = sum(scores) / match_count if match_count else 0.0
        best_idx = max(range(match_count), key=lambda i: scores[i]) if match_count else None
        best_chunk = chunks[best_idx] if best_idx is not None else None

        unique_results.append({
            "url": data["url"],
            "council_name": data["council_name"],
            "date": data["date"],
            "chunk_text": best_chunk,
            "score": avg_score if match_count else None,
            "match_count": match_count,
        })

    unique_results.sort(key=lambda item: (-item["match_count"], -(item["score"] or 0.0)))
    return unique_results[:final_top_k]


@app.post("/summary_search")
def summary_search(req: SearchRequest) -> List[Dict[str, Any]]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    top_k = max(1, min(100, req.top_k or 5))

    try:
        vec = provider.embed([req.query])[0]
    except Exception as e:
        logger.exception(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=f"embedding failed: {e}")
    vec_lit = vector_literal(vec)

    sql = text(
        """
        SELECT m.url, m.council_name, m.date, s.summary,
               1 - (s.embedding <=> CAST(:query_vec AS vector)) AS score
        FROM chunks_summary s
        JOIN meeting_metadata m ON s.doc_id = m.doc_id
        WHERE (:ministry IS NULL OR m.ministry = :ministry)
        ORDER BY s.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
        """
    )

    try:
        with engine.begin() as conn:
            rows = conn.execute(
                sql,
                {
                    "query_vec": vec_lit,
                    "ministry": req.ministry,
                    "top_k": top_k,
                },
            ).fetchall()
    except Exception as e:
        logger.exception(f"DB query failed: {e}")
        raise HTTPException(status_code=500, detail=f"db query failed: {e}")

    results: List[Dict[str, Any]] = []
    for r in rows:
        results.append(
            {
                "url": r[0],
                "council_name": r[1],
                "date": r[2].isoformat() if r[2] else None,
                "summary": r[3],
                "score": float(r[4]) if r[4] is not None else None,
            }
        )
    return results

