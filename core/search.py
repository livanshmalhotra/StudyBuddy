"""
core/search.py — hybrid_search(query, k) pure function
Vector search (pgvector cosine) + BM25 full-text (tsvector), merged via RRF.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from core.config import settings
from core.db import Session
from core.embedding import embed_batch

RRF_K = 60  # standard RRF constant


@dataclass
class SearchResult:
    chunk_id: int
    text: str
    filename: str
    page: Optional[int]
    heading: Optional[str]
    fused_score: float
    vector_rank: Optional[int]
    text_rank: Optional[int]
    margin: float   # fused_score[0] - fused_score[1], 0.0 if single result


def _rrf_merge(
    vec_rows: list[tuple],   # (id, score)
    fts_rows: list[tuple],   # (id, score)
    rrf_k: int = RRF_K,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = Σ 1 / (rrf_k + rank)."""
    scores: dict[int, float] = {}
    vec_ranks: dict[int, int] = {}
    fts_ranks: dict[int, int] = {}

    for rank, (chunk_id, _) in enumerate(vec_rows, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
        vec_ranks[chunk_id] = rank

    for rank, (chunk_id, _) in enumerate(fts_rows, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
        fts_ranks[chunk_id] = rank

    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_ids, vec_ranks, fts_ranks


def hybrid_search(query: str, k: int = 5) -> list[SearchResult]:
    """
    Runs vector + full-text search, merges with RRF, returns top-k results
    enriched with document metadata.
    """
    # 1. Embed the query
    query_vec = embed_batch([query])[0]
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    with Session() as session:
        # 2. Vector search — top 20 by cosine similarity
        vec_rows = session.execute(
            text("""
                SELECT c.id, 1 - (c.embedding <=> CAST(:vec AS vector)) AS score
                FROM chunks c
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> CAST(:vec AS vector)
                LIMIT 20
            """),
            {"vec": vec_str},
        ).fetchall()

        # 3. Full-text search — top 20 by ts_rank_cd
        fts_rows = session.execute(
            text("""
                SELECT c.id, ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q)) AS score
                FROM chunks c
                WHERE c.tsv @@ websearch_to_tsquery('english', :q)
                ORDER BY score DESC
                LIMIT 20
            """),
            {"q": query},
        ).fetchall()

        if not fts_rows:
            fts_rows = session.execute(
                text("""
                    SELECT c.id, ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) AS score
                    FROM chunks c
                    WHERE c.tsv @@ plainto_tsquery('english', :q)
                    ORDER BY score DESC
                    LIMIT 20
                """),
                {"q": query},
            ).fetchall()

        # 4. RRF merge
        if not vec_rows and not fts_rows:
            return []

        sorted_ids, vec_ranks, fts_ranks = _rrf_merge(
            [(r[0], r[1]) for r in vec_rows],
            [(r[0], r[1]) for r in fts_rows],
        )
        top_ids = [chunk_id for chunk_id, _ in sorted_ids[:k]]
        top_scores = {chunk_id: score for chunk_id, score in sorted_ids[:k]}

        # 5. Enrich with metadata
        if not top_ids:
            return []

        rows = session.execute(
            text("""
                SELECT c.id, c.text, c.page, c.heading, d.filename
                FROM chunks c
                JOIN documents d ON d.id = c.doc_id
                WHERE c.id = ANY(:ids)
            """),
            {"ids": top_ids},
        ).fetchall()

        by_id = {r[0]: r for r in rows}

        fused_scores = [s for _, s in sorted_ids[:k]]
        margin_val = (fused_scores[0] - fused_scores[1]) if len(fused_scores) > 1 else 0.0

        results = []
        for chunk_id in top_ids:
            if chunk_id not in by_id:
                continue
            row = by_id[chunk_id]
            results.append(SearchResult(
                chunk_id=chunk_id,
                text=row[1],
                page=row[2],
                heading=row[3],
                filename=row[4],
                fused_score=top_scores[chunk_id],
                vector_rank=vec_ranks.get(chunk_id),
                text_rank=fts_ranks.get(chunk_id),
                margin=margin_val,
            ))

    return results
