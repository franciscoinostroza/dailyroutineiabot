from telegram.ext import ContextTypes
from bot.services.ai import ai_assistant


async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    chat_id = str(update.effective_chat.id)

    await update.message.chat.send_action("typing")

    try:
        respuesta = await ai_assistant.process_message(texto, chat_id)
    except Exception as e:
        respuesta = f"Error al consultar la IA: {e}"

    await update.message.reply_text(respuesta)
