from telegram.ext import ContextTypes

from bot.tools.habitos import registrar_habito, ver_habitos


async def habitos(update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        result = await registrar_habito(" ".join(context.args))
        await update.message.reply_text(result)
    else:
        result = await ver_habitos()
        await update.message.reply_text(result)
