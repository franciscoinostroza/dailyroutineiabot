from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.tools.compras import dia_hoy_es, descuentos_del_dia, parsear_tope
from bot.services.sheets import get_worksheet

tz = pytz.timezone(settings.timezone)


async def compra(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "Uso:\n"
            "/compra <producto> <cantidad> <precio> <supermercado> <billetera>\n\n"
            "Ejemplo:\n"
            "/compra leche 3 1500 Coto Uala\n\n"
            "Supermercados: Coto, Carrefour, Dia\n"
            "Billeteras: MercadoPago, Brubank, Uala, PersonalPay"
        )
        return

    producto = args[0]
    supermercado = args[3]
    billetera = args[4]

    try:
        cantidad = float(args[1])
        precio_unit = float(args[2])
    except ValueError:
        await update.message.reply_text(
            "Cantidad y precio deben ser numeros.\n"
            "Ejemplo: /compra leche 3 1500 Coto Uala"
        )
        return

    fecha = datetime.now(tz).strftime("%Y-%m-%d")
    precio_total = cantidad * precio_unit
    dia_es = dia_hoy_es()

    descuento_row = next(
        (d for d in descuentos_del_dia(dia_es)
         if supermercado.lower() in str(d.get("supermercado", "")).lower()
         and billetera.lower() in str(d.get("billetera", "")).lower()),
        None
    )

    if descuento_row:
        pct = float(descuento_row.get("porcentaje", 0))
        tope = parsear_tope(descuento_row.get("tope"))
        ahorro_bruto = precio_total * pct / 100
        ahorro = min(ahorro_bruto, tope) if tope else ahorro_bruto
        precio_final = precio_total - ahorro
        tope_aviso = f" (tope ${tope:,.0f} — ahorro real ${ahorro:,.0f})" if tope and ahorro < ahorro_bruto else ""
    else:
        pct = ahorro = 0.0
        precio_final = precio_total
        tope_aviso = ""

    try:
        get_worksheet("Historial").append_row([
            fecha, producto, cantidad, precio_unit, precio_total,
            supermercado, billetera, pct, round(ahorro, 2), round(precio_final, 2),
        ])
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar en Sheets: {e}")
        return

    if descuento_row:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} → ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Descuento {pct:g}%{tope_aviso} → ahorras ${ahorro:,.0f}\n"
            f"  Total final: ${precio_final:,.0f} 💸"
        )
    else:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} → ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Sin descuento hoy para esa combinacion.\n"
            f"  Usa /descuentos para ver las mejores opciones de hoy."
        )
    await update.message.reply_text(msg)


async def descuentos(update, context: ContextTypes.DEFAULT_TYPE):
    dia_es = dia_hoy_es()
    filas = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(f"Sin descuentos registrados para hoy ({dia_es}).")
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    msg = f"💳 Descuentos del {dia_es}:\n\n"
    for d in filas_ord:
        tope = parsear_tope(d.get("tope"))
        notas = d.get("notas", "")
        tope_txt = f" — tope ${tope:,.0f}" if tope else " — sin tope"
        notas_txt = f"\n   ⚠️ {notas}" if notas else ""
        msg += f"⭐ {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{tope_txt}{notas_txt}\n"
    await update.message.reply_text(msg)


async def donde(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /donde <producto>\n"
            "Ejemplo: /donde arroz\n"
            "Te digo que super conviene hoy segun los descuentos."
        )
        return
    producto = " ".join(context.args)
    dia_es = dia_hoy_es()
    filas = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(
            f"No hay descuentos registrados para hoy ({dia_es}). Compra donde quieras."
        )
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    mejor = filas_ord[0]
    tope = parsear_tope(mejor.get("tope"))
    notas = mejor.get("notas", "")
    tope_txt = f" — tope ${tope:,.0f}" if tope else " — sin tope"
    notas_txt = f"\n⚠️ {notas}" if notas else ""

    msg = f"🛒 Para {producto} hoy ({dia_es}):\n\n"
    msg += f"Mejor: {mejor['supermercado']} con {mejor['billetera']} → {mejor['porcentaje']:g}%{tope_txt}{notas_txt}\n"
    if len(filas_ord) > 1:
        msg += "\nOtras opciones:\n"
        for d in filas_ord[1:]:
            t = parsear_tope(d.get("tope"))
            t_txt = f" — tope ${t:,.0f}" if t else " — sin tope"
            msg += f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}\n"
    await update.message.reply_text(msg)


async def gastos(update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            mes = context.args[0]
            datetime.strptime(mes, "%Y-%m")
        except ValueError:
            await update.message.reply_text("Formato invalido. Usa: /gastos 2026-05")
            return
    else:
        mes = datetime.now(tz).strftime("%Y-%m")

    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer Historial: {e}")
        return

    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        await update.message.reply_text(
            f"Sin compras registradas en {mes}.\n"
            "Registra compras con /compra."
        )
        return

    total_bruto = sum(float(r.get("precio_total", 0)) for r in filas)
    total_ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
    total_final = sum(float(r.get("precio_final", 0)) for r in filas)

    por_super: dict[str, float] = {}
    for r in filas:
        s = str(r.get("supermercado", "Otro"))
        por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))

    msg = (
        f"📊 Gastos {mes}\n\n"
        f"  Compras: {len(filas)}\n"
        f"  Total sin descuentos: ${total_bruto:,.0f}\n"
        f"  Ahorro total: ${total_ahorro:,.0f}\n"
        f"  Total pagado: ${total_final:,.0f}\n\n"
        "Por supermercado:\n"
    )
    for s, monto in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
        msg += f"  {s}: ${monto:,.0f}\n"
    await update.message.reply_text(msg)


async def historial_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    n = 10
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer Historial: {e}")
        return

    if not rows:
        await update.message.reply_text("Sin compras registradas aun. Usa /compra para registrar.")
        return

    ultimas = rows[-n:][::-1]
    msg = f"🧾 Ultimas {len(ultimas)} compras:\n\n"
    for r in ultimas:
        ahorro = float(r.get("ahorro", 0))
        ahorro_txt = f" (−${ahorro:,.0f})" if ahorro > 0 else ""
        msg += (
            f"  {r.get('fecha','')} — {r.get('producto','')} x{r.get('cantidad','')}\n"
            f"  {r.get('supermercado','')} con {r.get('billetera','')} → "
            f"${float(r.get('precio_final',0)):,.0f}{ahorro_txt}\n\n"
        )
    await update.message.reply_text(msg)
