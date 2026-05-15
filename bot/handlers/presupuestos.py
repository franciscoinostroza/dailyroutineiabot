from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.tools.presupuestos import (
    WorksheetPresupuestos, agregar_presupuesto, ver_presupuesto, verificar_alertas_presupuesto,
)

tz = pytz.timezone(settings.timezone)


async def presupuesto(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        msg = await ver_presupuesto()
        await update.message.reply_text(msg)
        return

    sub = context.args[0].lower()
    if sub == "agregar":
        if len(context.args) < 3:
            await update.message.reply_text(
                "Uso: /presupuesto agregar <categoria> <monto>\n"
                "Ejemplo: /presupuesto agregar Coto 150000"
            )
            return
        cat = context.args[1]
        try:
            monto = float(context.args[2])
        except ValueError:
            await update.message.reply_text("El monto debe ser un numero.")
            return
        result = await agregar_presupuesto(cat, monto)
        await update.message.reply_text(f"✅ {result}")
    elif sub == "alertas":
        alertas = await verificar_alertas_presupuesto()
        if not alertas:
            await update.message.reply_text("✅ Todos los presupuestos estan dentro del limite.")
        else:
            msg = "⚠️ Alertas de presupuesto:\n\n" + "\n".join(alertas)
            await update.message.reply_text(msg)
    elif sub in ("listar", "ver"):
        msg = await ver_presupuesto()
        await update.message.reply_text(msg)
    elif sub == "borrar":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /presupuesto borrar <categoria>")
            return
        cat = " ".join(context.args[1:])
        pres = WorksheetPresupuestos.find_by_categoria(cat)
        if pres is None:
            await update.message.reply_text(f"No encontre el presupuesto '{cat}'.")
            return
        ws = WorksheetPresupuestos.get()
        rows = ws.get_all_values()
        fila = next((i + 2 for i, r in enumerate(rows[1:]) if r[0].lower() == cat.lower()), None)
        if fila:
            ws.delete_rows(fila)
            await update.message.reply_text(f"🗑 Presupuesto eliminado: {cat}")
    else:
        await update.message.reply_text(
            "Uso:\n"
            "/presupuesto — Ver presupuestos\n"
            "/presupuesto agregar <cat> <monto>\n"
            "/presupuesto alertas — Ver alertas\n"
            "/presupuesto borrar <cat>"
        )
