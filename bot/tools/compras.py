import re
import logging
from datetime import datetime
from calendar import monthrange

import pytz

from bot.config import settings
from bot.services.sheets import get_worksheet

tz = pytz.timezone(settings.timezone)

DIA_EN_ES = {
    "monday": "lunes", "tuesday": "martes", "wednesday": "miercoles",
    "thursday": "jueves", "friday": "viernes", "saturday": "sabado", "sunday": "domingo",
}

SUPERMERCADOS_VALIDOS = ["Coto", "Carrefour", "Dia"]
BILLETERAS_VALIDAS = ["MercadoPago", "Brubank", "Uala", "PersonalPay", "Supervielle", "Banco Ciudad", "Banco del Sol", "Prex"]


def dia_hoy_es() -> str:
    return DIA_EN_ES[datetime.now(tz).strftime("%A").lower()]


def es_ultimo_sabado() -> bool:
    hoy = datetime.now(tz)
    if hoy.weekday() != 5:
        return False
    return hoy.day + 7 > monthrange(hoy.year, hoy.month)[1]


def parsear_tope(raw) -> float | None:
    if not raw or str(raw).strip().lower() in ("", "sin tope", "-"):
        return None
    nums = re.sub(r"[^\d]", "", str(raw))
    return float(nums) if nums else None


def descuentos_del_dia(dia_es: str) -> list[dict]:
    try:
        rows = get_worksheet("Descuentos").get_all_records()
    except Exception as e:
        logging.error(f"Error leyendo Descuentos: {e}")
        return []
    resultado = []
    for r in rows:
        d = str(r.get("dia", "")).lower()
        if d == dia_es:
            resultado.append(r)
        elif d == "sabado_ultimo" and dia_es == "sabado" and es_ultimo_sabado():
            resultado.append(r)
    return resultado


async def registrar_compra(
    producto: str, cantidad: float, precio_unitario: float,
    supermercado: str, billetera: str,
) -> str:
    cantidad = float(cantidad)
    precio_unit = float(precio_unitario)
    fecha = datetime.now(tz).strftime("%Y-%m-%d")
    precio_total = cantidad * precio_unit
    dia_es = dia_hoy_es()

    descuento_row = next(
        (d for d in descuentos_del_dia(dia_es)
         if supermercado.lower() in str(d.get("supermercado", "")).lower()
         and billetera.lower() in str(d.get("billetera", "")).lower()),
        None
    )

    pct = ahorro = 0.0
    tope_aviso = ""
    if descuento_row:
        pct = float(descuento_row.get("porcentaje", 0))
        tope = parsear_tope(descuento_row.get("tope"))
        ahorro_bruto = precio_total * pct / 100
        ahorro = min(ahorro_bruto, tope) if tope else ahorro_bruto
        tope_aviso = f" (tope ${tope:,.0f})" if tope and ahorro < ahorro_bruto else ""

    precio_final = precio_total - ahorro

    get_worksheet("Historial").append_row([
        fecha, producto, cantidad, precio_unit, precio_total,
        supermercado, billetera, pct, round(ahorro, 2), round(precio_final, 2),
    ])

    if descuento_row:
        return (
            f"Compra registrada: {producto} x{cantidad:g} a ${precio_unit:,.0f} c/u\n"
            f"Total bruto: ${precio_total:,.0f}\n"
            f"Descuento {supermercado}+{billetera}: {pct:g}%{tope_aviso}\n"
            f"Ahorro: ${ahorro:,.0f}\n"
            f"Total final: ${precio_final:,.0f}"
        )
    else:
        return (
            f"Compra registrada: {producto} x{cantidad:g} a ${precio_unit:,.0f} c/u\n"
            f"Total: ${precio_total:,.0f}\n"
            f"Sin descuento hoy para {supermercado}+{billetera}."
        )


async def ver_gastos() -> str:
    mes = datetime.now(tz).strftime("%Y-%m")
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception:
        return "Error al leer el historial de compras."
    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        return f"Sin compras en {mes}."
    total_bruto = sum(float(r.get("precio_total", 0)) for r in filas)
    total_ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
    total_final = sum(float(r.get("precio_final", 0)) for r in filas)
    por_super: dict[str, float] = {}
    for r in filas:
        s = str(r.get("supermercado", "Otro"))
        por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))
    lineas = [
        f"Gastos {mes}:",
        f"  Compras: {len(filas)}",
        f"  Total bruto: ${total_bruto:,.0f}",
        f"  Ahorro: ${total_ahorro:,.0f}",
        f"  Total pagado: ${total_final:,.0f}",
        "Por supermercado:",
    ]
    for s, m in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
        lineas.append(f"  {s}: ${m:,.0f}")
    return "\n".join(lineas)


async def ver_descuentos() -> str:
    dia_es = dia_hoy_es()
    filas = descuentos_del_dia(dia_es)
    if not filas:
        return f"Sin descuentos registrados para hoy ({dia_es})."
    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    lineas = [f"Descuentos de hoy ({dia_es}):"]
    for d in filas_ord:
        t = parsear_tope(d.get("tope"))
        t_txt = f" (tope ${t:,.0f})" if t else ""
        lineas.append(f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}")
    return "\n".join(lineas)
