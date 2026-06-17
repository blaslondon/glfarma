import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Ayudás a los empleados a resolver consultas de dispensación en el mostrador.

REGLAS CRÍTICAS:
1. PRESTADORES: buscá en la base local. Respondé "✅ figura (Mat. X)" o "❌ No figura"
2. COMISIONADOS: SIEMPRE mostrá primero los del listado comisionado GL Farma. Solo si no hay, mencioná otras marcas.
3. MÚLTIPLES DROGAS: cada droga es INDEPENDIENTE. NUNCA las combines. Tratá cada una por separado.
4. NORMAS: si no encontrás en la base local, buscá en colfarma.org.ar priorizando el boletín más reciente 2026.
5. Máximo 5 líneas. Sin advertencias innecesarias. Español rioplatense.

FORMATO RECETA COMPLETA:
👨‍⚕️ [Prestador] → ✅/❌
💊 [DROGA 1]: [comisionados]
💊 [DROGA 2]: [comisionados]"""


def search_droga(word):
    results = search_exact(word)
    vec = search_documents(f"comisionado droga {word}", n_results=3)
    seen = set(d["text"] for d in results)
    for d in vec:
        if d["text"] not in seen:
            results.append(d)
            seen.add(d["text"])
    return results[:3]


def search_knowledge_base(query: str, history: list = None) -> str:
    context_parts = []
    seen_texts = set()

    for doc in search_exact(query)[:3]:
        if doc["text"] not in seen_texts:
            context_parts.append(f"[PRESTADORES - {doc['source']}]\n{doc['text']}")
            seen_texts.add(doc["text"])

    for word in [w for w in query.split() if len(w) > 5]:
        for doc in search_droga(word)[:2]:
            if doc["text"] not in seen_texts:
                context_parts.append(f"[COMISIONADOS - {doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    if not context_parts:
        for doc in search_documents(query, n_results=5):
            if doc["text"] not in seen_texts:
                context_parts.append(f"[{doc['source']}]\n{doc['text']}")
                seen_texts.add(doc["text"])

    context = "\n\n---\n\n".join(context_parts[:7]) if context_parts else ""
    use_web_search = not context_parts

    messages = list(history[:-1]) if history else []
    prompt = f"""{"Datos GL Farma:" + chr(10) + context + chr(10) + "---" + chr(10) if context else "No encontré en la base local." + chr(10)}
Consulta: {query}{"" if context else chr(10) + "Buscá en colfarma.org.ar priorizando boletín más reciente 2026."}"""

    messages.append({"role": "user", "content": prompt})
    tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web_search else []

    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=400,
        system=SYSTEM_PROMPT,
        tools=tools if tools else anthropic.NOT_GIVEN,
        messages=messages
    )

    if response.stop_reason == "tool_use" and tools:
        messages.append({"role": "assistant", "content": response.content})
        tool_results = [{"type": "tool_result", "tool_use_id": b.id, "content": "ok"}
                        for b in response.content if b.type == "tool_use"]
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            response = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=400,
                system=SYSTEM_PROMPT, tools=tools, messages=messages
            )

    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    return "\n".join(text_parts) if text_parts else "❓ No encontré información."
