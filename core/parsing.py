import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator

try:
    import pymupdf as fitz  # use pymupdf directly
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pytesseract = None

# If TESSERACT_CMD is in env, configure it
if "TESSERACT_CMD" in os.environ and pytesseract:
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

OCR_MIN_CHARS = int(os.environ.get("OCR_MIN_CHARS", "50"))

@dataclass
class Page:
    page: int | None
    heading: str | None
    text: str

def parse(path: str | Path) -> list[Page]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext == ".pdf":
        return list(_parse_pdf(path))
    elif ext == ".docx":
        return list(_parse_docx(path))
    elif ext == ".md":
        return list(_parse_md(path))
    elif ext == ".txt":
        return list(_parse_txt(path))
    elif ext in (".png", ".jpg", ".jpeg"):
        return list(_parse_image(path))
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def _extract_pdf_heading(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    for line in lines[:3]:
        if re.search(r'^\s*page\s+\d+', line, re.IGNORECASE) or re.search(r'page\s+\d+\s+of\s+\d+', line, re.IGNORECASE):
            continue
        if len(line) <= 80 and not line.endswith("."):
            return line
    return None

def _parse_pdf(path: Path) -> Iterator[Page]:
    if not fitz:
        raise ImportError("pymupdf (fitz) is not installed")
    doc = fitz.open(path)
    for i, page in enumerate(doc):
        text = page.get_text()
        if len(text.strip()) < OCR_MIN_CHARS and pytesseract:
            # Try OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        
        heading = _extract_pdf_heading(text)
        yield Page(page=i, heading=heading, text=text)

def _parse_docx(path: Path) -> Iterator[Page]:
    if not docx:
        raise ImportError("python-docx is not installed")
    doc = docx.Document(path)
    text_blocks = []
    current_heading = None
    
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        if style_name.startswith("Heading") and para.text.strip():
            if text_blocks:
                yield Page(page=None, heading=current_heading, text="\n".join(text_blocks))
                text_blocks = []
            current_heading = para.text.strip()
        
        if para.text.strip():
            text_blocks.append(para.text.strip())
            
    if text_blocks:
        yield Page(page=None, heading=current_heading, text="\n".join(text_blocks))

def _parse_md(path: Path) -> Iterator[Page]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    text_blocks = []
    current_heading = None
    
    for line in lines:
        if line.startswith("#"):
            if text_blocks:
                yield Page(page=None, heading=current_heading, text="\n".join(text_blocks))
                text_blocks = []
            current_heading = line.lstrip("#").strip()
        text_blocks.append(line)
        
    if text_blocks:
        yield Page(page=None, heading=current_heading, text="\n".join(text_blocks))

def _parse_txt(path: Path) -> Iterator[Page]:
    text = path.read_text(encoding="utf-8")
    yield Page(page=None, heading=None, text=text)

def _parse_image(path: Path) -> Iterator[Page]:
    if not pytesseract:
        raise ImportError("pytesseract is not installed")
    img = Image.open(path)
    text = pytesseract.image_to_string(img)
    yield Page(page=None, heading=None, text=text)
