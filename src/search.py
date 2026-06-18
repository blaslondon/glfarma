import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Ayudás a los empleados a resolver consultas de dispensación en el mostrador.

REGLAS CRÍTICAS:
1. PRESTADORES: buscá en la base local. Respondé "✅ figura (Mat. X)" o "❌ No figura"
2. COMISIONADOS: SIEMPRE mostrá SOLO los del listado comisionado GL Farma. Si no hay, decí "Sin comisionados GL Farma". NUNCA sugieras marcas que no estén en el listado.
3. MÚLTIPLES DROGAS: cada droga es INDEPENDIENTE. NUNCA las combines. Tratá cada una por separado.
4. NORMAS Y BOLETINES: los boletines más recientes pisan las normas anteriores. Si hay conflicto, el boletín más nuevo tiene prioridad.
5. SI NO ENCONTRÁS: respondé SOLO "No encontré esa información. Consultá con tu supervisor de sucursal o con el supervisor de obras sociales de Lacarra." Sin links, teléfonos ni instrucciones adicionales.
6. Máximo 5 líneas. Sin advertencias innecesarias. Español rioplatense. Sin emojis de advertencia.

FORMATO RECETA:
👨‍⚕️ [Prestador] → ✅/❌
💊 [DROGA 1]: [solo comisionados GL Farma]
💊 [DROGA 2]: [solo comisionados GL Farma]"""


def search_droga(word):
    results = search_exact(word)
    vec = search_documents(f"comisionado droga {word}", n_results=3)
    seen = set(d["text"] for d in results)
    for d in vec:
        if d["text"] not in seen:
            results.append(d)
            seen.add(d["text"])
    return results[:3]


def is_comisionado_query(query):
    keywords = ["comision", "marca", "producto", "laboratorio", "generico", "q marca", "que marca"]
    return any(kw in query.lower() for kw in keywords)


def get_drug_words_from_history(history):
    if not history:
        return []
    words = []
    for msg in history[-4:]:
        content = msg.get("content", "")
        if isinstance(content, str):
            words.extend(w.strip('",.:') for w in content.split() if len(w) > 5)
    return list(set(words))


def search_knowledge_base(query: str, history: list = None) -> str:
    context_parts = []
    seen_texts = set()

    search_words = set(w.strip('",.:') for w in query.split() if len(w) > 4)
    if is_comisionado_query(query) and history:
        search_words.update(get_drug_words_from_history(history))

    for doc in search_exact(query)[:3]:
        if doc["text"] not in seen_texts:
            label = f"[{doc['doc_type'].upper()} {doc['date_score']} - {doc['source']}]"
            context_parts.append(f"{label}\n{doc['text']}")
            seen_texts.add(doc["text"])

    for word in search_words:
        for doc in search_droga(word)[:2]:
            if doc["text"] not in seen_texts:
                label = f"[COMISIONADOS - {doc['source']}]"
                context_parts.append(f"{label}\n{doc['text']}")
                seen_texts.add(doc["text"])

    if not context_parts:
        for doc in search_documents(query, n_results=6):
            if doc["text"] not in seen_texts:
                label = f"[{doc['doc_type'].upper()} {doc['date_score']} - {doc['source']}]"
                context_parts.append(f"{label}\n{doc['text']}")
                seen_texts.add(doc["text"])

    context = "\n\n---\n\n".join(context_parts[:8]) if context_parts else ""
    use_web_search = not context_parts

    messages = []
    if history and not is_comisionado_query(query):
        messages.extend(history[:-1])

    prompt = f"""{"Datos GL Farma (boletín más reciente pisa norma anterior):" + chr(10) + context + chr(10) + "---" if context else "No encontré en la base local."}

Consulta: {query}"""

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
    return "\n".join(text_parts) if text_parts else "No encontré esa información. Consultá con tu supervisor de sucursal o con el supervisor de obras sociales de Lacarra."
