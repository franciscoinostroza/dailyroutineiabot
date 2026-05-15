import io
import csv
import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_worksheet, WorksheetPagos, WorksheetTrabajo

tz = pytz.timezone(settings.timezone)


async def exportar_gastos(mes: str | None = None) -> io.BytesIO | None:
    if mes is None:
        mes = datetime.now(tz).strftime("%Y-%m")
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        logging.error(f"Error exportando gastos: {e}")
        return None

    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        return None

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["fecha", "producto", "cantidad", "precio_unitario", "precio_total",
                     "supermercado", "billetera", "descuento_pct", "ahorro", "precio_final"])
    for r in filas:
        writer.writerow([
            r.get("fecha", ""), r.get("producto", ""), r.get("cantidad", ""),
            r.get("precio_unitario", ""), r.get("precio_total", ""),
            r.get("supermercado", ""), r.get("billetera", ""),
            r.get("descuento_pct", ""), r.get("ahorro", ""), r.get("precio_final", ""),
        ])

    buf_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    buf_bytes.name = f"gastos_{mes}.csv"
    buf_bytes.seek(0)
    return buf_bytes


async def exportar_pagos() -> io.BytesIO | None:
    pagos = WorksheetPagos.read_all(solo_activos=False)
    if not pagos:
        return None

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["nombre", "monto", "dia_vencimiento", "categoria", "activo", "ultimo_mes"])
    for p in pagos:
        writer.writerow([
            p.get("nombre", ""), p.get("monto", ""), p.get("dia_vencimiento", ""),
            p.get("categoria", ""), p.get("activo", ""), p.get("ultimo_mes", ""),
        ])

    buf_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    buf_bytes.name = "pagos.csv"
    buf_bytes.seek(0)
    return buf_bytes


async def exportar_trabajo(mes: str | None = None) -> io.BytesIO | None:
    if mes is None:
        mes = datetime.now(tz).strftime("%Y-%m")
    rows = WorksheetTrabajo.read_all()
    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        return None

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["fecha", "proyecto", "hora_inicio", "hora_fin", "descripcion", "estado"])
    for r in filas:
        writer.writerow([
            r.get("fecha", ""), r.get("proyecto", ""), r.get("hora_inicio", ""),
            r.get("hora_fin", ""), r.get("descripcion", ""), r.get("estado", ""),
        ])

    buf_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    buf_bytes.name = f"trabajo_{mes}.csv"
    buf_bytes.seek(0)
    return buf_bytes
