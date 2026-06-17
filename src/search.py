import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Respondé consultas sobre prestadores de obras sociales y procedimientos internos.

REGLAS:
- Respondé MUY BREVEMENTE, máximo 3 líneas
- Si encontrás el dato exacto, decilo directo: "Sí, aparece" o "No aparece"
- Para prestadores: indicá nombre, tipo de matrícula y número si están disponibles
- No des recomendaciones ni listas de pasos
- Usá español rioplatense"""


def search_knowledge_base(query: str) -> str:
    docs = search_documents(query, n_results=6)
    exact_docs = search_exact(query)
    all_texts = []
    seen = set()
    for doc in (exact_docs + docs):
        if doc["text"] not in seen:
            seen.add(doc["text"])
            all_texts.append(doc)
    if not all_texts:
        return "❓ No encontré información sobre eso en la base de normas."
    context_parts = []
    sources = set()
    for doc in all_texts[:6]:
        context_parts.append(f"[{doc['source']}]\n{doc['text']}")
        sources.add(doc['source'])
    context = "\n\n---\n\n".join(context_parts)
    prompt = f"""Datos de la base GL Farma:\n\n{context}\n\n---\n\nConsulta: {query}"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.content[0].text
    source = next(iter(sources))
    return f"{answer}\n\n📄 {source}"
