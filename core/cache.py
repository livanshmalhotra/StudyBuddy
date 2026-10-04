"""
core/cache.py — Answer Cache DB Operations
Uses pgvector cosine similarity to cache and retrieve answers.
"""
from __future__ import annotations

import logging
from typing import Optional, Any
from sqlalchemy import text, Column, BigInteger, Text, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from core.config import settings
from core.db import Base, Session
from core.embedding import embed_batch

logger = logging.getLogger(__name__)


class AnswerCache(Base):
    __tablename__ = "answer_cache"

    id = Column(BigInteger, primary_key=True)
    q_embedding = Column(Vector(settings.EMBED_DIM))
    question = Column(Text)
    answer = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_cached_answer(query: str, threshold: float = 0.92) -> Optional[dict[str, Any]]:
    """
    Looks up similar cached question/answer pairs in answer_cache.
    Returns {"answer": str, "similarity": float} if similarity >= threshold, else None.
    """
    try:
        query_vec = embed_batch([query])[0]
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        with Session() as session:
            row = session.execute(
                text("""
                    SELECT answer, 1 - (q_embedding <=> CAST(:vec AS vector)) AS similarity
                    FROM answer_cache
                    WHERE q_embedding IS NOT NULL
                    ORDER BY q_embedding <=> CAST(:vec AS vector)
                    LIMIT 1
                """),
                {"vec": vec_str},
            ).fetchone()

            if row and row[1] is not None and row[1] >= threshold:
                logger.info(f"[Cache Hit] similarity={row[1]:.4f}")
                return {"answer": row[0], "similarity": float(row[1])}

    except Exception as exc:
        logger.warning(f"Answer cache lookup error: {exc}")

    return None


def cache_answer(query: str, answer: str) -> None:
    """
    Saves a question and synthesized answer into answer_cache table.
    """
    if not query or not answer:
        return

    try:
        query_vec = embed_batch([query])[0]
        with Session() as session:
            cache_entry = AnswerCache(
                q_embedding=query_vec,
                question=query.strip(),
                answer=answer.strip(),
            )
            session.add(cache_entry)
            session.commit()
            logger.info(f"[Cache Stored] Question: {query[:40]}...")
    except Exception as exc:
        logger.warning(f"Failed to store answer in cache: {exc}")
