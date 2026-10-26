"""Gemini embedding helpers shared by document ingestion and search."""

import os
import numpy as np
from google.genai import types

from services.ai_service import AIServiceError, get_gemini_client

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")


def embed_texts(texts, task_type):
    try:
        response = get_gemini_client().models.embed_content(
            model=EMBEDDING_MODEL, contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        vectors = [embedding.values for embedding in response.embeddings]
        if len(vectors) != len(texts):
            raise ValueError("Embedding count did not match input count")
        return np.asarray(vectors, dtype="float32")
    except AIServiceError:
        raise
    except Exception as exc:
        raise AIServiceError("Study material embeddings could not be created. Please try again.") from exc


def embed_documents(texts):
    return embed_texts(texts, "RETRIEVAL_DOCUMENT")


def embed_query(question):
    return embed_texts([question], "RETRIEVAL_QUERY")[0]
