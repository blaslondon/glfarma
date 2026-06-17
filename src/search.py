import os
import anthropic
from src.embeddings import search_documents, search_exact

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Sos un asistente interno de GL Farma, una cadena de farmacias en Argentina.
Ayudás a los empleados a resolver consultas de dispensación en el mostrador.

CASOS QUE MANEJÁS:

1. VERIFICAR PRESTADOR EN OBRA SOCIAL
   - Si preguntan si un médico/prestador está en cartilla, buscá en el listado de prestadores
   - Respondé: "✅ Sí, figura" o "❌ No figura" + matrícula si está disponible

2. PRODUCTOS COMISIONADOS POR DROGA
   - Si preguntan qué productos comisionan para una droga, buscá en el listado comisionado
   - Respondé con laboratorio y cantidad de SKUs

3. RECETA COMPLETA (caso más importante)
   - Si el empleado menciona una receta con obra social + médico/prestador + droga:
     a) Verificá si el prestador está en cartilla de esa obra social
     b) Listá los productos comisionados disponibles para esa droga
     c) Si el prestador NO está en cartilla, igual mostrá los productos comisionados
   - Formato:
     "👨‍⚕️ Prestador: [nombre] → ✅ en cartilla / ❌ no figura
      💊 Podés ofrecer: [producto 1 - lab], [producto 2 - lab]..."

REGLAS:
- Máximo 4 líneas
- Sin listas largas ni recomendaciones
- Español rioplatense
- Si no encontrás el dato, decí "No figura en la base" sin agregar nada más"""


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
        return "❓ No encontré información sobre eso en la base."
    context_parts = []
    for doc in all_texts[:8]:
        context_parts.append(f"[{doc['source']}]\n{doc['text']}")
    context = "\n\n---\n\n".join(context_parts)
    prompt = f"Datos de la base GL Farma:\n\n{context}\n\n---\n\nConsulta del empleado: {query}"
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=350,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
