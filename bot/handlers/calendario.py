from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.calendar import crear_evento, leer_eventos, eliminar_evento

tz = pytz.timezone(settings.timezone)

DIAS_MAP = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}

_ultimos_eventos: list[dict] = []


async def agenda_calendar(update, context: ContextTypes.DEFAULT_TYPE):
    global _ultimos_eventos
    hoy = datetime.now(tz).date()

    if not context.args:
        fecha = hoy
    else:
        arg = context.args[0].lower()
        if arg == "hoy":
            fecha = hoy
        elif arg in ("manana", "mañana"):
            fecha = hoy + timedelta(days=1)
        elif arg in DIAS_MAP:
            dias_hasta = (DIAS_MAP[arg] - hoy.weekday()) % 7
            dias_hasta = dias_hasta if dias_hasta > 0 else 7
            fecha = hoy + timedelta(days=dias_hasta)
        elif "/" in arg:
            try:
                dia, mes = arg.split("/")
                fecha = hoy.replace(day=int(dia), month=int(mes))
            except Exception:
                await update.message.reply_text(
                    "Formato invalido. Usa: /agenda hoy, manana, lunes, o 06/05"
                )
                return
        else:
            try:
                fecha = datetime.strptime(arg, "%Y-%m-%d").date()
            except ValueError:
                await update.message.reply_text(
                    "Formato invalido. Usa: /agenda hoy, manana, lunes, o 06/05"
                )
                return

    dia_str = fecha.strftime("%Y-%m-%d")
    dia_legible = fecha.strftime("%d/%m/%Y")

    try:
        eventos = leer_eventos(dia_str)
        _ultimos_eventos = eventos
        if not eventos:
            await update.message.reply_text(f"Sin eventos en el calendario para el {dia_legible}.")
            return
        msg = f"📅 Eventos del {dia_legible}:\n\n"
        for i, e in enumerate(eventos, 1):
            hora = e["start"].get("dateTime", e["start"].get("date", ""))
            hora = hora[11:16] if "T" in hora else "Todo el dia"
            msg += f"{i}. {hora} — {e.get('summary', 'Sin titulo')}\n"
        msg += "\nPara eliminar uno: /eliminar_evento <numero>"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def eliminar_evento_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    global _ultimos_eventos
    if not _ultimos_eventos:
        await update.message.reply_text(
            "Primero consulta los eventos con /agenda hoy (o el dia que quieras)."
        )
        return
    if not context.args:
        await update.message.reply_text(
            "Indica el numero del evento a eliminar.\nEjemplo: /eliminar_evento 1"
        )
        return
    try:
        indice = int(context.args[0]) - 1
        if indice < 0 or indice >= len(_ultimos_eventos):
            await update.message.reply_text(
                f"Numero invalido. Hay {len(_ultimos_eventos)} eventos."
            )
            return
        titulo = _ultimos_eventos[indice].get("summary", "Sin titulo")
        eliminar_evento(_ultimos_eventos[indice]["id"])
        _ultimos_eventos.pop(indice)
        await update.message.reply_text(f"🗑 Evento eliminado: {titulo}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def evento(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /evento <fecha> <hora_inicio> <hora_fin> <titulo>\n"
            "Ejemplo: /evento 2026-05-10 14:00 16:00 Reunion Workana"
        )
        return
    fecha = args[0]
    inicio = f"{fecha}T{args[1]}:00"
    fin = f"{fecha}T{args[2]}:00"
    titulo = " ".join(args[3:])
    try:
        crear_evento(titulo, inicio, fin)
        await update.message.reply_text(
            f"✅ Evento creado: {titulo}\n📅 {fecha} {args[1]} - {args[2]}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
