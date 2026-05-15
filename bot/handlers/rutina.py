from telegram.ext import ContextTypes
import logging

from bot.tools.presupuestos import verificar_alertas_presupuesto


async def callback_rutina_confirmacion(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("rutina_hecho_"):
        actividad = data.replace("rutina_hecho_", "").replace("_", " ")
        await query.edit_message_text(
            f"✅ Hecho: {actividad}\n\n{query.message.text}"
        )

    elif data.startswith("rutina_omitir_"):
        actividad = data.replace("rutina_omitir_", "").replace("_", " ")
        await query.edit_message_text(
            f"⏭ Omitido: {actividad}\n\n{query.message.text}"
        )


async def callback_rutina(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logging.info(f"Rutina callback: {query.data}")
