from telegram.ext import ContextTypes
from datetime import datetime
import pytz
import io

from bot.config import settings
from bot.tools.estadisticas import generar_grafico_gastos, generar_grafico_trabajo
from bot.tools.presupuestos import ver_presupuesto
from bot.tools.exportar import exportar_gastos, exportar_pagos, exportar_trabajo

tz = pytz.timezone(settings.timezone)


async def estadisticas(update, context: ContextTypes.DEFAULT_TYPE):
    meses = 3
    if context.args:
        try:
            meses = int(context.args[0])
        except ValueError:
            pass

    await update.message.reply_text("Generando estadisticas...")

    try:
        grafico = await generar_grafico_gastos(meses)
        if grafico:
            await update.message.reply_photo(
                photo=grafico,
                caption=f"📊 Gastos — ultimos {meses} meses"
            )
    except Exception as e:
        await update.message.reply_text(f"Error generando grafico de gastos: {e}")

    try:
        grafico = await generar_grafico_trabajo()
        if grafico:
            await update.message.reply_photo(
                photo=grafico,
                caption="⏱ Horas de trabajo este mes"
            )
    except Exception as e:
        await update.message.reply_text(f"Error generando grafico de trabajo: {e}")

    try:
        presup = await ver_presupuesto()
        await update.message.reply_text(presup)
    except Exception as e:
        await update.message.reply_text(f"Error leyendo presupuestos: {e}")


async def exportar(update, context: ContextTypes.DEFAULT_TYPE):
    tipo = "gastos"
    if context.args:
        tipo = context.args[0].lower()

    mes = None
    if len(context.args) > 1:
        mes = context.args[1]
        try:
            datetime.strptime(mes, "%Y-%m")
        except ValueError:
            await update.message.reply_text("Formato de mes invalido. Usa YYYY-MM (ej: 2026-05)")
            return

    await update.message.reply_text(f"Exportando {tipo}...")

    try:
        if tipo == "gastos":
            data = await exportar_gastos(mes)
            filename = f"gastos_{mes or datetime.now(tz).strftime('%Y-%m')}.csv"
        elif tipo == "pagos":
            data = await exportar_pagos()
            filename = "pagos.csv"
        elif tipo == "trabajo":
            data = await exportar_trabajo(mes)
            filename = f"trabajo_{mes or datetime.now(tz).strftime('%Y-%m')}.csv"
        else:
            await update.message.reply_text(
                "Tipo no reconocido. Usa: /exportar gastos|pagos|trabajo [YYYY-MM]"
            )
            return

        if data is None:
            await update.message.reply_text(f"No hay datos para exportar.")
            return

        await update.message.reply_document(
            document=data,
            filename=filename,
            caption=f"📎 {filename}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error exportando: {e}")
