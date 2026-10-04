"""
core/main.py — FastAPI application
Routes: /health, /search, /ingest, /documents, DELETE /documents/{filename}, /upload
Sentry init (no-op if SENTRY_DSN is blank).
"""
from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import sentry_sdk
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from core.config import settings
from core.db import Session, Document, Chunk
from core.embedding import embed_batch
from core.search import _rrf_merge, SearchResult


@contextmanager
def _noop_span():
    """Context manager used in place of sentry_sdk.start_span when Sentry is disabled."""
    yield

# ── Sentry (no-op when DSN is empty) ────────────────────────────────────────
if settings.SENTRY_DSN:
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=1.0,
    )

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="StudyBuddy API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic request/response models ─────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    k: int = 2
    synthesize: bool = True


class SearchResponse(BaseModel):
    chunk_id: int
    text: str
    filename: str
    page: Optional[int]
    heading: Optional[str]
    fused_score: float
    vector_rank: Optional[int]
    text_rank: Optional[int]
    margin: float
    llm_used: bool = False


class SearchResultPayload(BaseModel):
    ai_answer: Optional[str] = None
    gate_decision: str = "MEDIUM_LOW"
    cache_hit: bool = False
    results: list[SearchResponse]


class IngestRequest(BaseModel):
    path: str


class DocumentOut(BaseModel):
    id: int
    filename: str
    sha256: str
    status: str
    ingested_at: Optional[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search", response_model=SearchResultPayload)
def search(body: SearchRequest):
    """Hybrid vector + BM25 search + Answer Cache + Confidence Gate + Gemma Answer Synthesis."""
    try:
        from core.search import hybrid_search
        from core.cache import get_cached_answer
        from core.gate import evaluate_gate, GateConfidence
        from core.answer import synthesize_answer

        # 1. Answer Cache Lookup
        cached = get_cached_answer(body.query)
        if cached:
            results = hybrid_search(body.query, k=body.k)
            search_responses = [
                SearchResponse(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    filename=r.filename,
                    page=r.page,
                    heading=r.heading,
                    fused_score=r.fused_score,
                    vector_rank=r.vector_rank,
                    text_rank=r.text_rank,
                    margin=r.margin,
                    llm_used=False,
                )
                for r in results
            ]
            return SearchResultPayload(
                ai_answer=cached["answer"],
                gate_decision="CACHE_HIT",
                cache_hit=True,
                results=search_responses,
            )

        # 2. Hybrid Retrieval
        results = hybrid_search(body.query, k=body.k)
        if not results:
            return SearchResultPayload(
                ai_answer="Answer not found in your notes.",
                gate_decision="NO_MATCH",
                cache_hit=False,
                results=[],
            )

        # 3. Confidence Gate Evaluation
        gate_decision = evaluate_gate(results)

        ai_ans = None
        llm_used = False

        if body.synthesize and results:
            ai_ans = synthesize_answer(body.query, results, auto_cache=True)
            llm_used = bool(ai_ans)

        search_responses = [
            SearchResponse(
                chunk_id=r.chunk_id,
                text=r.text,
                filename=r.filename,
                page=r.page,
                heading=r.heading,
                fused_score=r.fused_score,
                vector_rank=r.vector_rank,
                text_rank=r.text_rank,
                margin=r.margin,
                llm_used=llm_used,
            )
            for r in results
        ]

        return SearchResultPayload(
            ai_answer=ai_ans,
            gate_decision=gate_decision.value if isinstance(gate_decision, GateConfidence) else str(gate_decision),
            cache_hit=False,
            results=search_responses,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ingest")
async def start_ingest(body: IngestRequest):
    """
    Starts a Temporal IngestWorkflow for the given file path.
    Falls back to direct ingest_file() if Temporal is unavailable (dev mode).
    """
    path = Path(body.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {body.path}")

    try:
        from temporalio.client import Client
        from temporalio.common import WorkflowIDReusePolicy
        from worker.workflows import IngestWorkflow
        import hashlib

        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        workflow_id = f"ingest-{sha256}"

        client = await Client.connect(settings.TEMPORAL_HOST)
        handle = await client.start_workflow(
            IngestWorkflow.run,
            str(path),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        )
        return {"workflow_id": workflow_id, "run_id": handle.result_run_id}

    except Exception:
        # Temporal not available — run synchronously (useful in dev without Docker)
        from core.ingest import ingest_file
        result = ingest_file(path)
        return {"workflow_id": None, "result": result}


@app.get("/documents", response_model=list[DocumentOut])
def list_documents():
    """List all ingested documents with their status."""
    with Session() as session:
        docs = session.query(Document).order_by(Document.ingested_at.desc()).all()
        return [
            DocumentOut(
                id=doc.id,
                filename=doc.filename,
                sha256=doc.sha256,
                status=doc.status,
                ingested_at=str(doc.ingested_at) if doc.ingested_at else None,
            )
            for doc in docs
        ]


@app.get("/documents/{filename}/details")
def get_document_details(filename: str):
    """Retrieve full metadata and extracted chunks for a document."""
    with Session() as session:
        doc = session.query(Document).filter_by(filename=filename).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
        
        chunks = session.query(Chunk).filter_by(doc_id=doc.id).order_by(Chunk.id.asc()).all()
        return {
            "id": doc.id,
            "filename": doc.filename,
            "sha256": doc.sha256,
            "status": doc.status,
            "ingested_at": str(doc.ingested_at) if doc.ingested_at else None,
            "chunk_count": len(chunks),
            "chunks": [
                {
                    "id": c.id,
                    "page": c.page,
                    "heading": c.heading,
                    "topic": c.topic,
                    "text": c.text,
                }
                for c in chunks
            ],
        }


@app.get("/documents/{filename}/file")
def get_document_file(filename: str):
    """Serve the raw file for inline PDF preview or download."""
    upload_dir = Path(settings.UPLOAD_DIR)
    file_path = upload_dir / filename
    if not file_path.exists():
        matches = list(upload_dir.glob(f"*{filename}*"))
        if matches:
            file_path = matches[0]
        else:
            raise HTTPException(status_code=404, detail=f"File '{filename}' not found on server")
    
    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else None
    return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    """
    Delete a document and ALL its context in safe dependency order:
      1. attempts  (no cascade — must delete manually first)
      2. questions (cascade via chunks, but safer to delete explicitly)
      3. answer_cache (full clear — it's just a cache)
      4. document  (cascade removes chunks automatically)
    """
    with Session() as session:
        doc = session.query(Document).filter_by(filename=filename).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")

        doc_id = doc.id

        # Count chunks before deletion (for response)
        chunk_count = session.execute(
            text("SELECT COUNT(*) FROM chunks WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        ).scalar() or 0

        # Step 1: Delete attempts that belong to questions from this document's chunks
        session.execute(text("""
            DELETE FROM attempts
            WHERE question_id IN (
                SELECT q.id FROM questions q
                JOIN chunks c ON c.id = q.chunk_id
                WHERE c.doc_id = :doc_id
            )
        """), {"doc_id": doc_id})

        # Step 2: Delete questions for this document's chunks
        session.execute(text("""
            DELETE FROM questions
            WHERE chunk_id IN (
                SELECT id FROM chunks WHERE doc_id = :doc_id
            )
        """), {"doc_id": doc_id})

        # Step 3: Clear the answer cache (pure cache — rebuilds on next search)
        session.execute(text("DELETE FROM answer_cache"))

        # Step 4: Delete the document — chunks cascade automatically
        session.execute(
            text("DELETE FROM documents WHERE id = :doc_id"),
            {"doc_id": doc_id},
        )
        session.commit()

    return {"deleted": filename, "chunks_removed": int(chunk_count)}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save uploaded file to UPLOAD_DIR (watchdog will pick it up)."""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "path": str(dest)}


# ── Day 2 Endpoints ─────────────────────────────────────────────────────────

class AttemptRequest(BaseModel):
    question_id: int
    topic: str
    correct: bool
    seconds_taken: int = 10


class ShortGradeRequest(BaseModel):
    question_id: int
    user_answer: str


class AgentChatRequest(BaseModel):
    thread_id: str = "default-thread"
    message: str


@app.get("/quiz")
def get_quiz(topic: Optional[str] = None, count: int = 5):
    """Retrieve practice questions for a topic."""
    from core.quiz import get_or_create_quiz
    return get_or_create_quiz(topic=topic, count=count)


@app.post("/attempts")
def post_attempt(body: AttemptRequest):
    """Log a quiz attempt for analytics and TabPFN weak-topic predictor."""
    from core.quiz import record_attempt
    return record_attempt(
        question_id=body.question_id,
        topic=body.topic,
        correct=body.correct,
        seconds_taken=body.seconds_taken,
    )


@app.post("/quiz/grade-short")
def grade_short(body: ShortGradeRequest):
    """Grade a free-text short answer response using Gemma LLM."""
    from core.grader import grade_short_answer
    return grade_short_answer(question_id=body.question_id, user_answer=body.user_answer)


@app.get("/weak-topics")
def weak_topics_endpoint():
    """Returns TabPFN predicted weak study topics."""
    from core.weak_topics import predict_weak_topics
    return predict_weak_topics()


@app.get("/stats")
def stats_endpoint():
    """Returns system operational metrics and % queries answered without LLM."""
    from core.stats import get_system_stats
    return get_system_stats()


@app.post("/agent/chat")
def agent_chat_endpoint(body: AgentChatRequest):
    """Mastra Agent router endpoint with tool execution and thread memory."""
    from core.agent import agent_chat
    return agent_chat(thread_id=body.thread_id, message=body.message)
