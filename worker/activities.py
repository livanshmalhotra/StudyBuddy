"""
worker/activities.py — Temporal activity implementations
Each activity is a thin wrapper around core/ pure functions.
Activities communicate via doc_id in the DB — no large payloads through Temporal.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import sentry_sdk
from temporalio import activity

from core.config import settings
from core.db import Session, Document, Chunk as ChunkModel
from core.parsing import parse
from core.chunking import chunk
from core.embedding import embed_batch


# ── Activity: hash_and_check ──────────────────────────────────────────────────
@activity.defn
async def hash_and_check(path: str) -> dict:
    """
    SHA-256 the file. If already in DB (same hash) → skip.
    If same filename exists → delete old doc (CASCADE drops chunks).
    Creates a new Document row with status='processing'.
    Returns: {"status": "skipped"|"new", "doc_id": int, "sha256": str}
    """
    with (sentry_sdk.start_span(op="hash_and_check") if settings.SENTRY_DSN else _noop()):
        file_path = Path(path)
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while data := f.read(65536):
                h.update(data)
        sha256 = h.hexdigest()

        with Session() as session:
            existing = session.query(Document).filter_by(sha256=sha256).first()
            if existing:
                return {"status": "skipped", "doc_id": existing.id, "sha256": sha256}

            old = session.query(Document).filter_by(filename=file_path.name).first()
            if old:
                session.delete(old)
                session.flush()

            doc = Document(filename=file_path.name, sha256=sha256, status="processing")
            session.add(doc)
            session.commit()
            session.refresh(doc)
            return {"status": "new", "doc_id": doc.id, "sha256": sha256}


# ── Activity: parse_activity ──────────────────────────────────────────────────
@activity.defn
async def parse_activity(args: dict) -> dict:
    """
    Parse the file into pages. Stores nothing — returns serialisable page data.
    Returns: {"pages": [{"page": int|None, "heading": str|None, "text": str}]}
    """
    with (sentry_sdk.start_span(op="parse") if settings.SENTRY_DSN else _noop()):
        path = Path(args["path"])
        pages = parse(path)
        return {
            "pages": [
                {"page": p.page, "heading": p.heading, "text": p.text}
                for p in pages
            ]
        }


# ── Activity: chunk_activity ──────────────────────────────────────────────────
@activity.defn
async def chunk_activity(args: dict) -> dict:
    """
    Chunk pre-parsed pages. Returns serialisable chunk data.
    Input: {"pages": [...]}  (from parse_activity output)
    Returns: {"chunks": [{"doc_page": int|None, "heading": str|None, "text": str, "token_count": int}]}
    """
    with (sentry_sdk.start_span(op="chunk") if settings.SENTRY_DSN else _noop()):
        from core.parsing import Page
        pages = [
            Page(page=p["page"], heading=p["heading"], text=p["text"])
            for p in args["pages"]
        ]
        chunks = chunk(pages)
        return {
            "chunks": [
                {"doc_page": c.doc_page, "heading": c.heading, "text": c.text, "token_count": c.token_count}
                for c in chunks
            ]
        }


# ── Activity: embed_activity ──────────────────────────────────────────────────
@activity.defn
async def embed_activity(args: dict) -> dict:
    """
    Embed chunk texts via Ollama.
    Input: {"chunks": [...]}
    Returns: {"vectors": [[float, ...], ...]}
    """
    with (sentry_sdk.start_span(op="embed") if settings.SENTRY_DSN else _noop()):
        texts = [c["text"] for c in args["chunks"]]
        vectors = embed_batch(texts)
        return {"vectors": vectors}


# ── Activity: upsert_activity ─────────────────────────────────────────────────
@activity.defn
async def upsert_activity(args: dict) -> dict:
    """
    Write chunks + embeddings to DB, mark document as 'ready'.
    Input: {"doc_id": int, "chunks": [...], "vectors": [[float]]}
    Returns: {"chunk_count": int}
    """
    with (sentry_sdk.start_span(op="upsert") if settings.SENTRY_DSN else _noop()):
        doc_id = args["doc_id"]
        chunks = args["chunks"]
        vectors = args["vectors"]

        with Session() as session:
            for c, vec in zip(chunks, vectors):
                session.add(ChunkModel(
                    doc_id=doc_id,
                    page=c["doc_page"],
                    heading=c["heading"],
                    text=c["text"],
                    embedding=vec,
                ))
            doc = session.query(Document).get(doc_id)
            if doc:
                doc.status = "ready"
            session.commit()

        return {"chunk_count": len(chunks)}


# ── Activity: tag_topic_activity ──────────────────────────────────────────────
@activity.defn
async def tag_topic_activity(args: dict) -> dict:
    """No-op placeholder. Day 2: k-means over embeddings."""
    return {"status": "noop"}


# ── Activity: pregen_questions_activity ───────────────────────────────────────
@activity.defn
async def pregen_questions_activity(args: dict) -> dict:
    """No-op placeholder. Day 2: generate MCQ questions from chunks."""
    return {"status": "noop"}


# ── Helper ────────────────────────────────────────────────────────────────────
from contextlib import contextmanager

@contextmanager
def _noop():
    yield
