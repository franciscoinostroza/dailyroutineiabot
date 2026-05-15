from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.tools.facturas import agregar_factura, ver_facturas, marcar_factura_cobrada

tz = pytz.timezone(settings.timezone)


async def factura(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        result = await ver_facturas()
        await update.message.reply_text(result)
        return

    sub = context.args[0].lower()

    if sub == "agregar":
        if len(context.args) < 4:
            await update.message.reply_text(
                "Uso: /factura agregar <cliente> <monto> <concepto> [ars|usd]\n"
                "Ejemplo: /factura agregar \"Cliente Y\" 500 \"Landing page + SEO\" usd"
            )
            return
        cliente = context.args[1]
        try:
            monto = float(context.args[2])
        except ValueError:
            await update.message.reply_text("Monto debe ser un numero.")
            return
        concepto = " ".join(context.args[3:-1]) if len(context.args) > 4 else context.args[3]
        moneda = context.args[-1].lower() if len(context.args) >= 5 and context.args[-1].lower() in ("usd", "ars") else "usd"
        result = await agregar_factura(cliente, monto, concepto, moneda)
        await update.message.reply_text(f"✅ {result}")

    elif sub == "listar":
        mes = context.args[1] if len(context.args) > 1 else None
        if mes:
            try:
                datetime.strptime(mes, "%Y-%m")
            except ValueError:
                mes = None
        result = await ver_facturas(mes)
        await update.message.reply_text(result)

    elif sub == "cobrada":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /factura cobrada <cliente>")
            return
        cliente = " ".join(context.args[1:])
        result = await marcar_factura_cobrada(cliente)
        await update.message.reply_text(f"✅ {result}")

    else:
        await update.message.reply_text(
            "Uso:\n"
            "/factura — Ver facturas del mes\n"
            "/factura agregar <cliente> <monto> <concepto> [usd|ars]\n"
            "/factura cobrada <cliente>\n"
            "/factura listar [YYYY-MM]"
        )
