from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import WorksheetPagos

tz = pytz.timezone(settings.timezone)


async def pago(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "💳 PAGOS Y SUSCRIPCIONES\n\n"
            "/pago agregar <nombre> <dia> <monto> [categoria]\n"
            "/pago listar — Ver todos\n"
            "/pago borrar <nombre>\n"
            "/pago pagado <nombre> — Marcar como pagado este mes\n"
            "/pagos — Proximos vencimientos\n\n"
            "Ejemplo: /pago agregar Netflix 15 3200 streaming"
        )
        return
    sub = context.args[0].lower()
    if sub == "agregar":
        await pago_agregar(update, context)
    elif sub == "listar":
        await pago_listar(update, context)
    elif sub == "borrar":
        await pago_borrar(update, context)
    elif sub == "pagado":
        await pago_pagado(update, context)
    else:
        await update.message.reply_text("Subcomando no reconocido. Usa: agregar, listar, borrar, pagado")


async def pago_agregar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /pago agregar <nombre> <dia> <monto> [categoria]\n"
            "Ejemplo: /pago agregar Netflix 15 3200 streaming"
        )
        return
    nombre = args[1]
    try:
        dia_venc = int(args[2])
        monto = float(args[3])
    except ValueError:
        await update.message.reply_text("Dia y monto deben ser numeros.")
        return
    if not (1 <= dia_venc <= 31):
        await update.message.reply_text("Dia de vencimiento: 1 a 31.")
        return
    categoria = " ".join(args[4:]) if len(args) > 4 else ""
    try:
        WorksheetPagos.append(nombre, monto, dia_venc, categoria)
        await update.message.reply_text(f"✅ Pago agregado: {nombre} — ${monto:,.0f} el dia {dia_venc}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def pago_listar(update, context: ContextTypes.DEFAULT_TYPE):
    pagos = WorksheetPagos.read_all(solo_activos=False)
    if not pagos:
        await update.message.reply_text("No hay pagos registrados. Agrega uno con /pago agregar")
        return
    msg = "💳 Pagos y suscripciones:\n\n"
    for p in sorted(pagos, key=lambda r: int(r.get("dia_vencimiento", 0))):
        activo = "✅" if str(p.get("activo", "si")).lower() != "no" else "❌"
        mes_pagado = str(p.get("ultimo_mes", ""))
        estado = f" (pagado {mes_pagado})" if mes_pagado else ""
        cat = f" [{p.get('categoria', '')}]" if p.get("categoria") else ""
        monto = float(p.get("monto", 0))
        msg += f"{activo} {p['nombre']}{cat} — ${monto:,.0f} — vence dia {p.get('dia_vencimiento','?')}{estado}\n"
    await update.message.reply_text(msg)


async def pago_borrar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /pago borrar <nombre>")
        return
    nombre = " ".join(args[1:])
    fila = WorksheetPagos.find_row(nombre)
    if fila is None:
        await update.message.reply_text(f"No encontre el pago '{nombre}'.")
        return
    try:
        WorksheetPagos.delete_row(fila)
        await update.message.reply_text(f"🗑 Pago eliminado: {nombre}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def pago_pagado(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /pago pagado <nombre>")
        return
    nombre = " ".join(args[1:])
    mes_actual = datetime.now(tz).strftime("%Y-%m")
    fila = WorksheetPagos.find_row(nombre)
    if fila is None:
        await update.message.reply_text(f"No encontre el pago '{nombre}'.")
        return
    try:
        WorksheetPagos.mark_paid(fila, mes_actual)
        await update.message.reply_text(f"✅ {nombre} marcado como pagado ({mes_actual}).")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def pagos_proximos_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    from bot.tools.resumen import pagos_proximos
    proximos = pagos_proximos(dias_ventana=settings.payments_reminder_window_days)
    if not proximos:
        await update.message.reply_text("Ningun pago proximo a vencer. Todo al dia!")
        return
    msg = "📅 Proximos vencimientos:\n\n"
    for p in proximos:
        dias = p["dias_faltan"]
        icono = "🔴" if dias == 0 else "🟡" if dias <= 2 else "🟢"
        label = "HOY" if dias == 0 else "manana" if dias == 1 else f"en {dias} dias"
        msg += f"{icono} {p['nombre']} — ${float(p.get('monto',0)):,.0f} — {label} (dia {p.get('dia_vencimiento','?')})\n"
    await update.message.reply_text(msg)
