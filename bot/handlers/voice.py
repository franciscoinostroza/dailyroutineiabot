import base64
import logging
import io

from telegram.ext import ContextTypes
from telegram import Voice

from bot.config import settings
from bot.services.ai import openai_client, ai_assistant


async def handle_voice(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    voice: Voice = update.message.voice

    await update.message.chat.send_action("typing")

    try:
        voice_file = await context.bot.get_file(voice.file_id)
        audio_bytes = io.BytesIO()
        await voice_file.download_to_memory(audio_bytes)
        audio_bytes.seek(0)
    except Exception as e:
        logging.error(f"Error descargando audio: {e}")
        await update.message.reply_text("No pude descargar el audio. Proba de nuevo.")
        return

    try:
        transcription = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.ogg", audio_bytes, "audio/ogg"),
            language="es",
        )
        texto = transcription.text.strip()
        logging.info(f"Whisper transcribio: {texto}")
    except Exception as e:
        logging.error(f"Error transcribiendo audio: {e}")
        await update.message.reply_text("No pude entender el audio. Proba de nuevo o escribime.")
        return

    if not texto:
        await update.message.reply_text("No entendi nada en el audio. ¿Me lo escribis?")
        return

    await update.message.reply_text(f"🎤 *{texto}*", parse_mode="Markdown")

    try:
        respuesta = await ai_assistant.process_message(texto, chat_id)
    except Exception as e:
        respuesta = f"Error al procesar: {e}"

    await update.message.reply_text(respuesta)
