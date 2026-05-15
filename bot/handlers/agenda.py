from telegram.ext import ContextTypes

from bot.tools.rutina import MENSAJES_DIA, RESUMEN, DIAS_VALIDOS, cargar_agenda
from bot.services.sheets import get_worksheet
from bot.services.auth import reset_auth_cache
from bot.config import settings


async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    from .basics import dia_hoy_es
    dia_es = dia_hoy_es()
    texto = RESUMEN.get(dia_es)
    if not texto:
        await update.message.reply_text(
            f"No hay resumen para hoy ({dia_es}).\n"
            "Si la agenda esta vacia usa /recargar para sincronizar desde Google Sheets."
        )
        return
    await update.message.reply_text(texto)


async def listar(update, context: ContextTypes.DEFAULT_TYPE):
    if not MENSAJES_DIA:
        await update.message.reply_text(
            "La agenda esta vacia. Proba con /recargar para sincronizar desde Google Sheets."
        )
        return
    texto = "📋 Agenda completa:\n\n"
    for dia in DIAS_VALIDOS:
        if dia not in MENSAJES_DIA:
            continue
        texto += f"{dia.upper()}:\n"
        for h, m, msg in sorted(MENSAJES_DIA[dia]):
            corto = (msg[:60] + "…") if len(msg) > 60 else msg
            texto += f"  {h:02d}:{m:02d} — {corto}\n"
        texto += "\n"
    await update.message.reply_text(texto)


async def recargar(update, context: ContextTypes.DEFAULT_TYPE):
    reset_auth_cache()
    ok, err = cargar_agenda()
    if ok:
        dias = len(MENSAJES_DIA)
        total = sum(len(v) for v in MENSAJES_DIA.values())
        await update.message.reply_text(
            f"✅ Agenda recargada: {total} recordatorios en {dias} dias.\n"
            "Los mensajes automaticos se actualizan al reiniciar el bot."
        )
    else:
        creds_set = "SI" if settings.google_creds_json else "NO"
        sheet_set = "SI" if settings.sheet_id else "NO"
        await update.message.reply_text(
            f"❌ Error conectando con Google Sheets:\n\n{err}\n\n"
            f"GOOGLE_CREDENTIALS configurado: {creds_set}\n"
            f"SHEET_ID configurado: {sheet_set}"
        )


async def agregar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /agregar <dia> <hora> <minuto> <mensaje>\n"
            f"Dias validos: {', '.join(DIAS_VALIDOS)}\n"
            "Ejemplo: /agregar lunes 10 0 Tomar medicacion"
        )
        return
    dia = args[0].lower()
    if dia not in DIAS_VALIDOS:
        await update.message.reply_text(f"Dia invalido. Usa uno de:\n{', '.join(DIAS_VALIDOS)}")
        return
    try:
        hora, minuto = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Hora y minuto deben ser numeros enteros.")
        return
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        await update.message.reply_text("Hora: 0-23. Minuto: 0-59.")
        return
    mensaje = " ".join(args[3:])
    try:
        get_worksheet("Agenda").append_row([dia, hora, minuto, mensaje])
        cargar_agenda()
        await update.message.reply_text(
            f"✅ Recordatorio agregado:\n  {dia.capitalize()} {hora:02d}:{minuto:02d} — {mensaje}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar en Sheets: {e}")


async def borrar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "Uso: /borrar <dia> <hora> <minuto>\n"
            "Ejemplo: /borrar lunes 10 0"
        )
        return
    dia = args[0].lower()
    try:
        hora, minuto = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Hora y minuto deben ser numeros.")
        return
    try:
        ws = get_worksheet("Agenda")
        rows = ws.get_all_values()
        fila = next(
            (i + 2 for i, r in enumerate(rows[1:])
             if r[0].lower() == dia and str(r[1]) == str(hora) and str(r[2]) == str(minuto)),
            None
        )
        if fila is None:
            await update.message.reply_text(
                f"No encontre un recordatorio el {dia} a las {hora:02d}:{minuto:02d}.\n"
                "Usa /listar para ver los horarios exactos."
            )
            return
        ws.delete_rows(fila)
        cargar_agenda()
        await update.message.reply_text(f"🗑 Eliminado: {dia.capitalize()} {hora:02d}:{minuto:02d}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
