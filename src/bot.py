import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.search import search_knowledge_base

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy el asistente de GL Farma.\n\n"
        "Podés consultarme sobre normas de obras sociales y procedimientos internos.\n\n"
        "Simplemente escribí tu pregunta y te respondo."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *¿Cómo usarme?*\n\n"
        "Escribí tu consulta directamente, por ejemplo:\n"
        "• ¿Cuál es el procedimiento para OSDE?\n"
        "• ¿Cómo se procesa una receta de PAMI?\n"
        "• ¿Qué documentación pide Swiss Medical?\n\n"
        "Busco en la base de normas actualizada y te respondo.",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    query = update.message.text
    logger.info(f"Consulta de {user.first_name}: {query}")

    await update.message.reply_text("🔍 Buscando...")

    try:
        response = search_knowledge_base(query)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error procesando consulta: {e}")
        await update.message.reply_text(
            "❌ Hubo un error procesando tu consulta. Intentá de nuevo en unos segundos."
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()
