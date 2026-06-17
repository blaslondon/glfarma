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
PARA NORMAS DE OBRAS SOCIALES: respondé con la info relevante de forma concisa
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
    # Búsqueda local primero
    context_parts = []
    prestador_docs = search_exact(query)
    seen_texts = set()
    for doc in prestador_docs[:3]:
        if doc["text"] not in seen_texts:
            context_parts.append(f"[PRESTADORES - {doc['source']}]\n{doc['text']}")
            seen_texts.add(doc["text"])

    words = [w for w in query.split() if len(w) > 5]
    for word in words:
        drug_docs = search_droga(word)
        for doc in drug_docs[:2]:
            if doc["text"] not in seen_texts:
                context_parts.append(f"[COMISIONADOS - {doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    if not context_parts:
        docs = search_documents(query, n_results=5)
        for doc in docs:
            if doc["text"] not in seen_texts:
                context_parts.append(f"[{doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    context = "\n\n---\n\n".join(context_parts[:7]) if context_parts else ""

    prompt = f"""Sos un asistente interno de GL Farma. Respondé en máximo 4 líneas, sin advertencias, en español rioplatense.

{"Datos de la base GL Farma:" + chr(10) + context + chr(10) + chr(10) + "---" + chr(10) if context else ""}

Consulta del empleado: {query}

Si no encontrás la info en la base local, buscá en colfarma.org.ar para responder sobre normas de obras sociales."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    # Extraer texto de la respuesta (puede incluir tool use)
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    # Si usó web search, hacer segunda llamada con los resultados
    if response.stop_reason == "tool_use":
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.content}
        ]
        # Agregar resultados de tool
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Búsqueda completada"
                })
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            response2 = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=SYSTEM_PROMPT,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=messages
            )
            text_parts = [b.text for b in response2.content if hasattr(b, "text")]

    return "\n".join(text_parts) if text_parts else "❓ No encontré información sobre eso."
