import os
import anthropic
from embeddings import search_documents

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Tu rol es responder consultas de empleados sobre normas de obras sociales, procedimientos internos y requisitos de prestadores.

Respondé en base al contexto provisto. Si la información no está en el contexto, indicalo claramente.
Usá un tono profesional pero cercano. Respondé en español rioplatense."""


def search_knowledge_base(query: str) -> str:
    # 1. Buscar documentos relevantes
    docs = search_documents(query, n_results=4)

    if not docs:
        return (
            "❓ No encontré información sobre eso en la base de normas.\n\n"
            "Puede que el documento aún no haya sido cargado. "
            "Consultá con tu supervisor o revisá el procedimiento manualmente."
        )

    # 2. Armar contexto
    context_parts = []
    sources = set()
    for doc in docs:
        context_parts.append(f"[{doc['source']} - pág. {doc['page']}]\n{doc['text']}")
        sources.add(doc['source'])

    context = "\n\n---\n\n".join(context_parts)

    # 3. Consultar Claude
    prompt = f"""Contexto de la base de normas GL Farma:

{context}

---

Consulta del empleado: {query}

Respondé basándote en el contexto. Si hay información específica sobre el tema, citá la fuente."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    answer = response.content[0].text

    # 4. Agregar fuentes al pie
    sources_text = "\n".join(f"• {s}" for s in sorted(sources))
    return f"{answer}\n\n📄 *Fuentes consultadas:*\n{sources_text}"
