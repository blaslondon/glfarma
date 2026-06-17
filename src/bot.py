import os
import base64
import logging
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.search import search_knowledge_base

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el asistente de GL Farma.\n\n"
        "Podés consultarme sobre:\n"
        "• Prestadores en cartilla de obras sociales\n"
        "• Productos comisionados por droga\n"
        "• 📷 Mandame una foto de la receta"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Ejemplos:*\n\n"
        "• instituto quirurgico callao, losartan\n"
        "• ¿Itoiz está en Unión Personal?\n"
        "• ¿Qué productos comisionan para ibuprofeno?\n"
        "• 📷 Foto de la receta",
        parse_mode="Markdown"
    )


async def process_image(image_data: bytes, mime_type: str, update: Update):
    """Extrae datos de una imagen de receta y consulta la base."""
    import anthropic
    encoded = base64.b64encode(image_data).decode("utf-8")
    ac = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    extraction = ac.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": encoded}},
            {"type": "text", "text": """Extraé de esta receta médica:
1. Obra social / cobertura
2. Médico o prestador (nombre)
3. Droga o medicamento (principio activo preferentemente)

Respondé SOLO con este formato exacto:
OBRA_SOCIAL: [valor o NO_FIGURA]
MEDICO: [valor o NO_FIGURA]
DROGA: [valor o NO_FIGURA]"""}
        ]}]
    )

    extracted = extraction.content[0].text
    logger.info(f"Receta extraída: {extracted}")

    lines = {}
    for line in extracted.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            lines[k.strip()] = v.strip()

    parts = [v for v in lines.values() if v and v != "NO_FIGURA"]

    if not parts:
        await update.message.reply_text("❓ No pude leer los datos. Escribilos manualmente.")
        return

    query = ", ".join(parts)
    await update.message.reply_text(f"🔍 Busco: {query}")
    response = search_knowledge_base(query)
    await update.message.reply_text(response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Analizando la receta...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(file.file_path)
        await process_image(resp.content, "image/jpeg", update)
    except Exception as e:
        logger.error(f"Error en foto: {e}")
        await update.message.reply_text("❌ Error procesando la foto.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Analizando la receta...")
    try:
        doc = update.message.document
        mime = doc.mime_type or "image/jpeg"
        file = await context.bot.get_file(doc.file_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(file.file_path)
        await process_image(resp.content, mime, update)
    except Exception as e:
        logger.error(f"Error en documento: {e}")
        await update.message.reply_text("❌ Error procesando el archivo.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    query = update.message.text
    logger.info(f"Consulta de {user.first_name}: {query}")
    await update.message.reply_text("🔍 Buscando...")
    try:
        response = search_knowledge_base(query)
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
