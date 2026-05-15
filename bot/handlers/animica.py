from telegram.ext import ContextTypes
from bot.tools.animica import WorksheetAnimica


async def animica(update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].lower() in ("bien", "maso", "mal"):
        WorksheetAnimica.upsert(context.args[0].lower())
        nota = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        if nota:
            WorksheetAnimica.upsert(context.args[0].lower(), nota)
        emojis = {"bien": "😊", "maso": "😐", "mal": "😞"}
        await update.message.reply_text(f"{emojis.get(context.args[0].lower(),'')} Anotado. Gracias por compartir.")
    else:
        result = WorksheetAnimica.get_streak()
        await update.message.reply_text(result)


async def handle_mood_callback(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "mood_bien":
        WorksheetAnimica.upsert("bien")
        await query.edit_message_text(
            query.message.text + "\n\n😊 ¡Bien ahi! Guardado. Mañana mas y mejor."
        )
    elif data == "mood_maso":
        WorksheetAnimica.upsert("maso")
        await query.edit_message_text(
            query.message.text + "\n\n😐 Anotado. Mañana sera otro dia."
        )
    elif data == "mood_mal":
        WorksheetAnimica.upsert("mal")
        await query.edit_message_text(
            query.message.text + "\n\n😞 Guardado. Si necesitas algo, aca estoy."
        )
    elif data == "mood_nota":
        await query.edit_message_text(
            query.message.text + "\n\n📝 Dale, escribime la nota. Ej: /animica bien Hoy termine el proyecto"
        )
