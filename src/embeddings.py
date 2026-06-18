import os
import unicodedata
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = os.environ.get("CHROMA_PATH", "/tmp/chroma")
COLLECTION_NAME = "glfarma_normas"

os.makedirs(CHROMA_PATH, exist_ok=True)

_client = None
_collection = None


def normalize(text: str) -> str:
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def get_chroma_client():
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"}
        )
    return _client, _collection


def add_document(doc_id: str, text: str, metadata: dict):
    _, collection = get_chroma_client()
    collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])


def search_documents(query: str, n_results: int = 6):
    _, collection = get_chroma_client()
    count = collection.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=n_results)
    docs = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        docs.append({
            "text": doc,
            "source": meta.get("source", "Desconocido"),
            "page": meta.get("page", "?"),
            "doc_type": meta.get("doc_type", "documento"),
            "date_score": int(meta.get("date_score", 0) or 0)
        })
    docs.sort(key=lambda x: x.get("date_score", 0), reverse=True)
    return docs


def search_exact(query: str):
    _, collection = get_chroma_client()
    if collection.count() == 0:
        return []
    keywords = [normalize(w) for w in query.split() if len(w) > 3]
    if not keywords:
        return []
    results = []
    seen = set()
    for kw in keywords:
        for variant in [kw, kw.lower(), kw.capitalize()]:
            try:
                res = collection.get(where_document={"$contains": variant})
                for i, doc in enumerate(res["documents"]):
                    if doc not in seen:
                        seen.add(doc)
                        meta = res["metadatas"][i]
                        results.append({
                            "text": doc,
                            "source": meta.get("source", "Desconocido"),
                            "page": meta.get("page", "?"),
                            "doc_type": meta.get("doc_type", "documento"),
                            "date_score": int(meta.get("date_score", 0) or 0)
                        })
            except Exception:
                pass
    results.sort(key=lambda x: x.get("date_score", 0), reverse=True)
    return results[:6]
