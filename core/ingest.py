import hashlib
from pathlib import Path
from core.db import Session, Document, Chunk
from core.parsing import parse
from core.chunking import chunk
from core.embedding import embed_batch

def hash_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk_data := f.read(8192):
            h.update(chunk_data)
    return h.hexdigest()

def ingest_file(path: str | Path) -> dict:
    """
    Pure synchronous function. No Temporal, no FastAPI.
    Returns {"status": "skipped" | "ingested" | "reingest", "doc_id": int}
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
        
    sha256 = hash_file(path)

    with Session() as session:
        existing = session.query(Document).filter_by(sha256=sha256).first()
        if existing:
            return {"status": "skipped", "doc_id": existing.id}

        old_by_name = session.query(Document).filter_by(filename=path.name).first()
        if old_by_name:
            session.delete(old_by_name)   # CASCADE deletes chunks
            session.flush()

        doc = Document(filename=path.name, sha256=sha256, status="processing")
        session.add(doc)
        session.flush()   # get doc.id

        pages = parse(path)
        chunks = chunk(pages)
        texts = [c.text for c in chunks]
        
        # embed text chunks
        vectors = embed_batch(texts)

        for c, vec in zip(chunks, vectors):
            session.add(Chunk(doc_id=doc.id, page=c.doc_page, heading=c.heading, text=c.text, embedding=vec))

        doc.status = "ready"
        session.commit()

        return {"status": "reingest" if old_by_name else "ingested", "doc_id": doc.id}
