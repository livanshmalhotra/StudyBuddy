import os
from core.parsing import parse
from core.chunking import chunk, CHUNK_MAX_TOKENS

def test_chunk_md(fixtures_dir):
    pages = parse(fixtures_dir / "sample.md")
    chunks = chunk(pages)
    
    assert len(chunks) > 0
    for c in chunks:
        assert c.text
        assert c.token_count <= CHUNK_MAX_TOKENS + 20

def test_chunk_pdf(fixtures_dir):
    pages = parse(fixtures_dir / "sample.pdf")
    chunks = chunk(pages)
    
    assert len(chunks) > 0
    for c in chunks:
        assert c.text
        assert c.token_count <= CHUNK_MAX_TOKENS + 20

def test_chunk_page_tracking():
    from core.parsing import Page
    p0 = Page(page=0, heading="P0", text=" ".join([f"p0word{i}" for i in range(300)]))
    p1 = Page(page=1, heading="P1", text=" ".join([f"p1word{i}" for i in range(300)]))
    chunks = chunk([p0, p1])
    assert len(chunks) >= 2
    page_numbers = {c.doc_page for c in chunks}
    assert 0 in page_numbers
    assert 1 in page_numbers

def test_chunk_oversized_unpunctuated_text():
    from core.parsing import Page
    # Create 1000 words without any period/punctuation
    long_text = " ".join([f"word{i}" for i in range(1000)])
    page = Page(page=0, heading="Large Block", text=long_text)
    chunks = chunk([page])
    assert len(chunks) > 1
    for c in chunks:
        assert c.token_count <= CHUNK_MAX_TOKENS + 20
        assert c.doc_page == 0

