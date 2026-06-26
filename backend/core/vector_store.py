"""Vector store for code embeddings."""
import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import faiss
from .code_chunker import CodeChunk


class VectorStore:
    def __init__(self):
        print("Loading embedding model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index: Optional[faiss.Index] = None
        self.chunks: List[CodeChunk] = []

    def build_index(self, chunks: List[CodeChunk]):
        if not chunks:
            return

        self.chunks = chunks

        texts = []
        for chunk in chunks:
            prefix = "Project documentation overview: " if chunk.file_path.lower().endswith('readme.md') else ""
            text = f"{prefix}File: {chunk.file_path}\nType: {chunk.chunk_type}\nName: {chunk.name}\n\n{chunk.content[:1500]}"
            texts.append(text)

        print(f"Embedding {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=False, batch_size=32)
        embeddings = np.array(embeddings).astype('float32')
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
        print(f"Index built with {len(chunks)} chunks")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if self.index is None or not self.chunks:
            return []

        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')
        faiss.normalize_L2(query_embedding)

        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            results.append({
                'content': chunk.content,
                'file_path': chunk.file_path,
                'start_line': chunk.start_line,
                'end_line': chunk.end_line,
                'chunk_type': chunk.chunk_type,
                'name': chunk.name,
                'language': chunk.language,
                'relevance_score': float(score)
            })

        # Prefer matches above threshold; always return top results for small indexes
        threshold = 0.05 if len(self.chunks) < 50 else 0.12
        filtered = [r for r in results if r['relevance_score'] > threshold]
        if not filtered:
            filtered = results[:min(3, len(results))]
        return filtered[:top_k]

    def clear(self):
        self.index = None
        self.chunks = []


vector_store = VectorStore()
