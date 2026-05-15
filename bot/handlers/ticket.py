import base64
import logging
import io

from telegram.ext import ContextTypes

from bot.config import settings
from bot.services.ai import openai_client


async def handle_ticket_photo(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    await update.message.chat.send_action("typing")
    await update.message.reply_text("📸 Procesando ticket... Dame unos segundos.")

    photo = update.message.photo[-1]
    try:
        photo_file = await context.bot.get_file(photo.file_id)
        img_bytes = io.BytesIO()
        await photo_file.download_to_memory(img_bytes)
        img_bytes.seek(0)
        img_base64 = base64.b64encode(img_bytes.read()).decode("utf-8")
    except Exception as e:
        logging.error(f"Error descargando foto: {e}")
        await update.message.reply_text("No pude descargar la foto. Proba de nuevo.")
        return

    system_prompt = (
        "Sos un OCR especializado en tickets de supermercado argentinos. "
        "Extrae todos los productos, cantidades y precios de la imagen. "
        "Responde SOLO en formato JSON sin texto adicional:\n"
        '{"supermercado": "Coto|Carrefour|Dia|Otro", '
        '"productos": [{"nombre": "...", "cantidad": 1, "precio_unitario": 100.0}]}\n'
        "Si no ves el nombre del super en el ticket, usa 'Otro'. "
        "Los precios deben ser numeros, no strings. Si no podes leer algo, no lo incluyas."
    )

    try:
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                ],
            }],
            max_tokens=1000,
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        logging.error(f"Error procesando ticket con OpenAI: {e}")
        await update.message.reply_text(f"Error al procesar la imagen: {e}")
        return

    import json
    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(raw[json_start:json_end])
        else:
            await update.message.reply_text("No pude leer el ticket. Proba con otra foto mas clara.")
            return
    except json.JSONDecodeError:
        logging.error(f"Respuesta no es JSON: {raw}")
        await update.message.reply_text("El ticket no se pudo interpretar bien. ¿Me pasas los datos?")
        return

    supermercado = data.get("supermercado", "Otro")
    productos = data.get("productos", [])

    if not productos:
        await update.message.reply_text("No encontre productos en la foto. Proba con mas luz.")
        return

    from bot.tools.compras import dia_hoy_es, descuentos_del_dia, parsear_tope
    from bot.services.sheets import get_worksheet
    from datetime import datetime
    import pytz
    tz = pytz.timezone(settings.timezone)

    fecha = datetime.now(tz).strftime("%Y-%m-%d")
    dia_es = dia_hoy_es()
    billetera = "MercadoPago"

    total_bruto = 0.0
    total_ahorro = 0.0

    for p in productos:
        nombre = str(p.get("nombre", ""))
        cantidad = float(p.get("cantidad", 1))
        precio_unit = float(p.get("precio_unitario", 0))
        precio_total = cantidad * precio_unit
        total_bruto += precio_total

        descuento_row = next(
            (d for d in descuentos_del_dia(dia_es)
             if supermercado.lower() in str(d.get("supermercado", "")).lower()
             and billetera.lower() in str(d.get("billetera", "")).lower()),
            None
        )
        pct = ahorro = 0.0
        if descuento_row:
            pct = float(descuento_row.get("porcentaje", 0))
            tope = parsear_tope(descuento_row.get("tope"))
            ahorro_bruto = precio_total * pct / 100
            ahorro = min(ahorro_bruto, tope) if tope else ahorro_bruto
        precio_final = precio_total - ahorro
        total_ahorro += ahorro

        get_worksheet("Historial").append_row([
            fecha, nombre, cantidad, precio_unit, precio_total,
            supermercado, billetera, pct, round(ahorro, 2), round(precio_final, 2),
        ])

    total_final = total_bruto - total_ahorro
    msg = f"🧾 Ticket procesado — {supermercado}:\n\n"
    for p in productos:
        n = p.get("nombre", "?")
        c = p.get("cantidad", 1)
        pu = p.get("precio_unitario", 0)
        msg += f"  • {n} x{c} → ${float(pu) * float(c):,.0f}\n"
    msg += "  " + "─" * 20 + "\n"
    msg += f"  Total bruto: ${total_bruto:,.0f}\n"
    if total_ahorro > 0:
        pct_descuento = descuento_row.get("porcentaje", 0) if descuento_row else 0
        msg += f"  Descuento {supermercado}+{billetera}: {pct_descuento:g}% → ahorro ${total_ahorro:,.0f}\n"
    msg += f"  Total final: ${total_final:,.0f} 💸"

    await update.message.reply_text(msg)
