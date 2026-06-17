import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Ayudás a los empleados a resolver consultas de dispensación en el mostrador.

REGLAS CRÍTICAS:
1. PRESTADORES: buscá en la base local. Respondé "✅ figura (Mat. X)" o "❌ No figura"
2. COMISIONADOS: SIEMPRE mostrá primero los productos del listado comisionado de GL Farma. Solo si no hay comisionados, mencioná otras marcas.
3. RECETA CON MÚLTIPLES DROGAS: cada droga es INDEPENDIENTE. NUNCA combines drogas de distintos renglones. Tratá cada una por separado.
4. NORMAS DE OBRAS SOCIALES: si no encontrás en la base local, podés buscar en colfarma.org.ar. Solo usá web search para normas/novedades, NUNCA para prestadores ni comisionados.
5. Máximo 5 líneas. Sin advertencias innecesarias. Español rioplatense.

FORMATO PARA RECETA COMPLETA:
👨‍⚕️ [Prestador] → ✅/❌
💊 [DROGA 1]: [comisionados primero]
💊 [DROGA 2]: [comisionados primero]"""


def search_droga(word: str) -> list:
    results = search_exact(word)
    vec = search_documents(f"comisionado droga {word}", n_results=3)
    seen = set(d["text"] for d in results)
    for d in vec:
        if d["text"] not in seen:
            results.append(d)
            seen.add(d["text"])
    return results[:3]


def is_norma_query(query: str) -> bool:
    keywords = ["norma", "novedad", "cambio", "actualiz", "vigente", "cobertura",
                "autoriza", "requiere", "necesita", "boletin", "informacion",
                "coseguro", "plan", "dispensa", "recetario", "validaci"]
    q = query.lower()
    return any(kw in q for kw in keywords)


def search_knowledge_base(query: str) -> str:
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
    use_web_search = is_norma_query(query) and not context_parts

    prompt = f"""{"Datos de la base GL Farma:" + chr(10) + context + chr(10) + chr(10) + "---" + chr(10) if context else "No encontré datos en la base local." + chr(10)}

Consulta: {query}"""

    tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web_search else []

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        tools=tools if tools else anthropic.NOT_GIVEN,
        messages=[{"role": "user", "content": prompt}]
    )

    if response.stop_reason == "tool_use" and tools:
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response.content}
        ]
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
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages
            )

    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    return "\n".join(text_parts) if text_parts else "❓ No encontré información sobre eso."
