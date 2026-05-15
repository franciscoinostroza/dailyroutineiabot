from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import WorksheetPagos

tz = pytz.timezone(settings.timezone)


async def agregar_pago(nombre: str, dia_vencimiento: int, monto: float, categoria: str = "") -> str:
    dia_venc = int(dia_vencimiento)
    monto = float(monto)
    if not (1 <= dia_venc <= 31):
        return f"Dia de vencimiento invalido: {dia_venc}. Debe ser 1-31."
    WorksheetPagos.append(nombre, monto, dia_venc, categoria)
    return f"Pago agregado: {nombre} — ${monto:,.0f} vence el dia {dia_venc} de cada mes."


async def marcar_pago_pagado(nombre: str) -> str:
    mes_actual = datetime.now(tz).strftime("%Y-%m")
    fila = WorksheetPagos.find_row(nombre)
    if fila is None:
        return f"No se encontro el pago '{nombre}'."
    WorksheetPagos.mark_paid(fila, mes_actual)
    return f"{nombre} marcado como pagado ({mes_actual})."


async def ver_pagos() -> str:
    pagos = WorksheetPagos.read_all(solo_activos=False)
    if not pagos:
        return "No hay pagos registrados."
    lineas = ["Pagos y suscripciones:"]
    for p in sorted(pagos, key=lambda r: int(r.get("dia_vencimiento", 0))):
        activo = "✅" if str(p.get("activo", "si")).lower() != "no" else "❌"
        pagado = f" (pagado {p['ultimo_mes']})" if p.get("ultimo_mes") else ""
        lineas.append(
            f"{activo} {p['nombre']} — ${float(p.get('monto', 0)):,.0f} — "
            f"dia {p.get('dia_vencimiento', '?')}{pagado}"
        )
    return "\n".join(lineas)
