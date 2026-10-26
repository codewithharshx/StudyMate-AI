"""Coordinates upload ingestion, retrieval, and grounded answer generation."""

import os
from werkzeug.utils import secure_filename

from rag.document_processor import chunk_pages, extract_document
from rag.embeddings import embed_documents, embed_query
from rag.vector_store import VectorStore
from services.ai_service import AIServiceError, generate_with_gemini

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_FILE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "txt"}
store = VectorStore()


class RAGServiceError(Exception):
    """Friendly RAG-specific error."""


def process_upload(uploaded_file):
    filename = secure_filename(uploaded_file.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise RAGServiceError("Please upload a PDF or TXT study file.")
    file_bytes = uploaded_file.read()
    if not file_bytes:
        raise RAGServiceError("Your study material appears to be empty.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise RAGServiceError(f"That file is too large. Please upload a file smaller than {MAX_UPLOAD_SIZE_MB} MB.")
    try:
        pages = extract_document(file_bytes, filename)
    except ValueError as exc:
        raise RAGServiceError(str(exc)) from exc
    chunks = chunk_pages(pages, filename)
    if not chunks:
        raise RAGServiceError("Your study material appears to be empty.")
    try:
        embeddings = embed_documents([chunk["text"] for chunk in chunks])
        store.clear_and_add(embeddings, chunks)
    except Exception as exc:
        if isinstance(exc, (RAGServiceError, AIServiceError)):
            raise
        raise RAGServiceError("The study material could not be indexed. Please try again.") from exc
    return {"filename": filename, "chunks": len(chunks)}


def ask_question(question):
    if store.index is None:
        raise RAGServiceError("Please upload study material before asking a question.")
    try:
        chunks = store.search(embed_query(question), top_k=4)
    except AIServiceError:
        raise
    except Exception as exc:
        raise RAGServiceError("Relevant study material could not be retrieved. Please try again.") from exc
    if not chunks:
        raise RAGServiceError("No relevant study material was found. Please upload your notes again.")
    context = "\n\n".join(f"[Source: {chunk['filename']}, page {chunk['page']}]\n{chunk['text']}" for chunk in chunks)
    prompt = f"""Study material context:\n{context}\n\nQuestion:\n{question}\n\nAnswer based only on the provided study material."""
    answer = generate_with_gemini(prompt, "You are a study assistant. Answer only using the supplied study material. Do not invent facts. If the answer is not supported by the context, clearly say it was not found in the provided study material. Use concise, student-friendly language.", 900, 0.2)
    sources, seen = [], set()
    for chunk in chunks:
        key = (chunk["filename"], chunk["page"])
        if key not in seen:
            sources.append({"filename": chunk["filename"], "page": chunk["page"]})
            seen.add(key)
    return {"answer": answer, "sources": sources}
