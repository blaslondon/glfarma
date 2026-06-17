import os
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = os.environ.get("CHROMA_PATH", "data/chroma")
COLLECTION_NAME = "glfarma_normas"

os.makedirs(CHROMA_PATH, exist_ok=True)

_client = None
_collection = None


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
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata]
    )


def search_documents(query: str, n_results: int = 4):
    _, collection = get_chroma_client()
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    docs = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        docs.append({
            "text": doc,
            "source": meta.get("source", "Desconocido"),
            "page": meta.get("page", "?")
        })
    return docs
