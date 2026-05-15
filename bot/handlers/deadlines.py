from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.tools.deadlines import agregar_deadline, ver_deadlines, WorksheetDeadlines

tz = pytz.timezone(settings.timezone)


async def deadline(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        result = await ver_deadlines()
        await update.message.reply_text(result)
        return

    sub = context.args[0].lower()

    if sub == "agregar":
        if len(context.args) < 3:
            await update.message.reply_text(
                "Uso: /deadline agregar <proyecto> <fecha YYYY-MM-DD> [notas]\n"
                "Ejemplo: /deadline agregar \"Web Cliente X\" 2026-05-25 \"Entrega final\""
            )
            return
        proyecto = context.args[1]
        fecha = context.args[2]
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except ValueError:
            await update.message.reply_text("Formato de fecha invalido. Usa YYYY-MM-DD.")
            return
        notas = " ".join(context.args[3:]) if len(context.args) > 3 else ""
        result = await agregar_deadline(proyecto, fecha, notas)
        await update.message.reply_text(f"✅ {result}")

    elif sub == "entregado":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /deadline entregado <proyecto>")
            return
        proyecto = " ".join(context.args[1:])
        WorksheetDeadlines.mark_delivered(proyecto)
        await update.message.reply_text(
            f"✅ {proyecto} marcado como entregado.\n\n"
            f"🎉 TREMENDO. Otro proyecto cerrado. ¿Cuantos van este mes?"
        )

    elif sub == "borrar":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /deadline borrar <proyecto>")
            return
        proyecto = " ".join(context.args[1:])
        WorksheetDeadlines.delete_row(proyecto)
        await update.message.reply_text(f"🗑 Deadline eliminado: {proyecto}")

    elif sub == "listar":
        result = await ver_deadlines()
        await update.message.reply_text(result)

    else:
        await update.message.reply_text(
            "Uso:\n"
            "/deadline — Ver deadlines activos\n"
            "/deadline agregar <proy> <fecha> [notas]\n"
            "/deadline entregado <proy>\n"
            "/deadline borrar <proy>"
        )
