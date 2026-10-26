"""Minimal in-memory FAISS store. It is intentionally replaceable later."""

import faiss
import numpy as np


class VectorStore:
    def __init__(self):
        self.index = None
        self.metadata = []

    def clear_and_add(self, embeddings, metadata):
        vectors = np.asarray(embeddings, dtype="float32").copy()
        faiss.normalize_L2(vectors)
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        self.metadata = list(metadata)

    def search(self, query_embedding, top_k=4):
        if self.index is None or not self.metadata:
            return []
        query = np.asarray([query_embedding], dtype="float32").copy()
        faiss.normalize_L2(query)
        _scores, indexes = self.index.search(query, min(top_k, len(self.metadata)))
        return [self.metadata[index] for index in indexes[0] if index >= 0]
