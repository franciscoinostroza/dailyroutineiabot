from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.calendar import leer_eventos
from bot.tools.compras import dia_hoy_es, descuentos_del_dia

tz = pytz.timezone(settings.timezone)


async def callback_botones(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "agenda_hoy":
        dia_str = datetime.now(tz).strftime("%Y-%m-%d")
        dia_legible = datetime.now(tz).strftime("%d/%m/%Y")
        try:
            eventos = leer_eventos(dia_str)
            if not eventos:
                await query.edit_message_text(f"Sin eventos hoy ({dia_legible}).")
            else:
                msg = f"📅 Eventos del {dia_legible}:\n\n"
                for i, e in enumerate(eventos, 1):
                    hora = e["start"].get("dateTime", "")
                    hora = hora[11:16] if "T" in hora else "Todo el dia"
                    msg += f"{i}. {hora} — {e.get('summary', 'Sin titulo')}\n"
                await query.edit_message_text(msg)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif query.data == "agenda_manana":
        manana = datetime.now(tz) + timedelta(days=1)
        dia_str = manana.strftime("%Y-%m-%d")
        dia_legible = manana.strftime("%d/%m/%Y")
        try:
            eventos = leer_eventos(dia_str)
            if not eventos:
                await query.edit_message_text(f"Sin eventos manana ({dia_legible}).")
            else:
                msg = f"📅 Eventos del {dia_legible}:\n\n"
                for i, e in enumerate(eventos, 1):
                    hora = e["start"].get("dateTime", "")
                    hora = hora[11:16] if "T" in hora else "Todo el dia"
                    msg += f"{i}. {hora} — {e.get('summary', 'Sin titulo')}\n"
                await query.edit_message_text(msg)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif query.data == "descuentos_hoy":
        dia_es = dia_hoy_es()
        filas = descuentos_del_dia(dia_es)
        if not filas:
            await query.edit_message_text(f"Sin descuentos para hoy ({dia_es}).")
        else:
            filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
            msg = f"💳 Descuentos del {dia_es}:\n\n"
            for d in filas_ord:
                msg += f"⭐ {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%\n"
            await query.edit_message_text(msg)

    elif query.data == "briefing_trabajar":
        from bot.tools.trabajo import iniciar_trabajo_tool
        await query.edit_message_text(query.message.text + "\n\n⏱ Dale, decime en que proyecto arrancas y lo registro.")
        await query.answer()

    elif query.data == "briefing_tareas":
        from bot.tools.recordatorios import ver_recordatorios_pendientes
        tareas = await ver_recordatorios_pendientes()
        await query.edit_message_text(query.message.text + f"\n\n📋 {tareas}")
        await query.answer()
