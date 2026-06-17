import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Ayudás a los empleados a resolver consultas de dispensación en el mostrador.

FORMATO DE RESPUESTA:
- Máximo 4 líneas
- Sin advertencias ni recomendaciones
- Español rioplatense

PARA PRESTADORES: "👨‍⚕️ [Nombre] → ✅ figura (Mat. [tipo] [número])" o "❌ No figura"
PARA COMISIONADOS: "💊 [DROGA] — [Lab1], [Lab2]..." 
PARA RECETA COMPLETA: primero prestador, después comisionados"""


def search_droga(word: str) -> list:
    results = search_exact(word)
    vec = search_documents(f"comisionado droga {word}", n_results=3)
    seen = set(d["text"] for d in results)
    for d in vec:
        if d["text"] not in seen:
            results.append(d)
            seen.add(d["text"])
    return results[:3]


def search_knowledge_base(query: str) -> str:
    context_parts = []

    # Búsqueda de prestador (exact match en cartilla)
    prestador_docs = search_exact(query)
    seen_texts = set()
    for doc in prestador_docs[:3]:
        if doc["text"] not in seen_texts:
            context_parts.append(f"[PRESTADORES - {doc['source']}]\n{doc['text']}")
            seen_texts.add(doc["text"])

    # Búsqueda de droga — palabras de más de 5 letras
    words = [w for w in query.split() if len(w) > 5]
    for word in words:
        drug_docs = search_droga(word)
        for doc in drug_docs[:2]:
            if doc["text"] not in seen_texts:
                context_parts.append(f"[COMISIONADOS - {doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    # Si no encontró nada, búsqueda vectorial general
    if not context_parts:
        docs = search_documents(query, n_results=5)
        for doc in docs:
            if doc["text"] not in seen_texts:
                context_parts.append(f"[{doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    if not context_parts:
        return "❓ No encontré información sobre eso en la base."

    context = "\n\n---\n\n".join(context_parts[:7])
    prompt = f"Datos de la base GL Farma:\n\n{context}\n\n---\n\nConsulta del empleado: {query}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=350,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
