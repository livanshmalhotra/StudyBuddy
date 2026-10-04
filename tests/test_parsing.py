from core.parsing import parse

def test_parse_md(fixtures_dir):
    pages = parse(fixtures_dir / "sample.md")
    assert len(pages) > 0
    assert pages[0].heading == "Introduction"
    assert "This is a test markdown file" in pages[0].text
    
def test_parse_txt(fixtures_dir):
    pages = parse(fixtures_dir / "sample.txt")
    assert len(pages) == 1
    assert pages[0].heading is None
    assert "This is plain text" in pages[0].text

def test_parse_pdf(fixtures_dir):
    pages = parse(fixtures_dir / "sample.pdf")
    assert len(pages) == 2
    assert pages[0].page == 0
    assert "First Heading" in pages[0].text
    # Heading extraction logic might extract "First Heading"
    assert pages[0].heading == "First Heading" or pages[0].heading is None

def test_parse_docx(fixtures_dir):
    pages = parse(fixtures_dir / "sample.docx")
    assert len(pages) > 0
    assert "Docx Heading" in pages[0].heading
    assert "This is a paragraph in docx." in pages[0].text
