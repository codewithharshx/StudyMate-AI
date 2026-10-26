"""PDF/TXT extraction, cleanup, and overlap-aware chunking."""

import re

try:
    import pymupdf as fitz
except ImportError:
    import fitz


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_document(file_bytes, filename):
    if filename.lower().endswith(".txt"):
        try:
            return [(clean_text(file_bytes.decode("utf-8")), 1)]
        except UnicodeDecodeError:
            return [(clean_text(file_bytes.decode("latin-1")), 1)]
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [(clean_text(page.get_text()), page_number + 1) for page_number, page in enumerate(document)]
        document.close()
        return pages
    except Exception as exc:
        raise ValueError("This PDF could not be read. Please upload a valid PDF file.") from exc


def chunk_pages(pages, filename, chunk_words=650, overlap_words=80):
    """Split each page into readable chunks while preserving source metadata."""
    chunks = []
    for text, page in pages:
        words = text.split()
        start = 0
        while start < len(words):
            part = " ".join(words[start:start + chunk_words]).strip()
            if part:
                chunks.append({"text": part, "filename": filename, "page": page, "chunk_index": len(chunks)})
            start += chunk_words - overlap_words
    return chunks
