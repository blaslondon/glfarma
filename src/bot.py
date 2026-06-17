import os
import base64
import logging
import httpx
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.search import search_knowledge_base

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
user_history = {}
MAX_HISTORY = 10

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=MAX_HISTORY)
    return list(user_history[user_id])

def add_to_history(user_id, role, content):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=MAX_HISTORY)
    user_history[user_id].append({"role": role, "content": content})

async def start(update, context):
    user_history.pop(update.message.from_user.id, None)
    await update.message.reply_text("👋 ¡Hola! Soy el asistente de GL Farma.\n\nPodés consultarme sobre:\n• Prestadores en cartilla\n• Productos comisionados\n• Normas de obras sociales\n• 📷 Foto de la receta")

async def help_command(update, context):
    await update.message.reply_text("📋 *Ejemplos:*\n\n• instituto quirurgico callao, losartan\n• ioma acepta recetas uma?\n• ¿Qué comisiona para ibuprofeno?\n• 📷 Foto de la receta", parse_mode="Markdown")

async def process_image(image_data, mime_type, update, user_id):
    import anthropic
    encoded = base64.b64encode(image_data).decode("utf-8")
    ac = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    extraction = ac.messages.create(
        model="claude-sonnet-4-6", max_tokens=300,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": encoded}},
            {"type": "text", "text": "Extraé de esta receta:\nOBRA_SOCIAL: [valor o NO_FIGURA]\nMEDICO: [valor o NO_FIGURA]\nDROGA_1: [valor o NO_FIGURA]\nDROGA_2: [valor o NO_FIGURA]\nRespondé SOLO con ese formato."}
        ]}]
    )
    extracted = extraction.content[0].text
    lines = {}
    for line in extracted.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            lines[k.strip()] = v.strip()
    parts = [v for k, v in lines.items() if v and v != "NO_FIGURA"]
    if not parts:
        await update.message.reply_text("❓ No pude leer los datos. Escribilos manualmente.")
        return
    query = ", ".join(parts)
    await update.message.reply_text(f"🔍 Busco: {query}")
    history = get_history(user_id)
    add_to_history(user_id, "user", f"[Foto de receta] {query}")
    response = search_knowledge_base(query, history)
    add_to_history(user_id, "assistant", response)
    await update.message.reply_text(response)

async def handle_photo(update, context):
    await update.message.reply_text("📷 Analizando la receta...")
    user_id = update.message.from_user.id
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        async with httpx.AsyncClient() as c:
            resp = await c.get(file.file_path)
        await process_image(resp.content, "image/jpeg", update, user_id)
    except Exception as e:
        logger.error(f"Error foto: {e}")
        await update.message.reply_text("❌ Error procesando la foto.")

async def handle_document(update, context):
    await update.message.reply_text("📷 Analizando la receta...")
    user_id = update.message.from_user.id
    try:
        doc = update.message.document
        mime = doc.mime_type or "image/jpeg"
        file = await context.bot.get_file(doc.file_id)
        async with httpx.AsyncClient() as c:
            resp = await c.get(file.file_path)
        await process_image(resp.content, mime, update, user_id)
    except Exception as e:
        logger.error(f"Error doc: {e}")
        await update.message.reply_text("❌ Error procesando el archivo.")

async def handle_message(update, context):
    user = update.message.from_user
    query = update.message.text
    user_id = user.id
    logger.info(f"Consulta de {user.first_name}: {query}")
    await update.message.reply_text("🔍 Buscando...")
    history = get_history(user_id)
    add_to_history(user_id, "user", query)
    try:
        response = search_knowledge_base(query, history)
        add_to_history(user_id, "assistant", response)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Hubo un error. Intentá de nuevo.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
