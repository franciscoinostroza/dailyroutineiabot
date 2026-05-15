import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetFacturas:
    HEADERS = ["cliente", "fecha", "monto", "moneda", "concepto", "estado"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Facturas", WorksheetFacturas.HEADERS, rows=200, cols=8)

    @staticmethod
    def read_all(mes: str | None = None) -> list[dict]:
        try:
            rows = WorksheetFacturas.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Facturas: {e}")
            return []
        if mes:
            rows = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
        return rows

    @staticmethod
    def append(cliente: str, fecha: str, monto: float, moneda: str,
               concepto: str, estado: str = "pendiente"):
        WorksheetFacturas.get().append_row([cliente, fecha, monto, moneda, concepto, estado])


async def agregar_factura(cliente: str, monto: float, concepto: str,
                          moneda: str = "usd", estado: str = "pendiente") -> str:
    fecha = datetime.now(tz).strftime("%Y-%m-%d")
    WorksheetFacturas.append(cliente, fecha, float(monto), moneda, concepto, estado)
    simbolo = "$" if moneda == "ars" else "USD"
    return f"Factura registrada: {cliente} — {simbolo} {float(monto):,.0f} — {concepto}"


async def ver_facturas(mes: str | None = None) -> str:
    if mes is None:
        mes = datetime.now(tz).strftime("%Y-%m")

    facturas = WorksheetFacturas.read_all(mes)
    if not facturas:
        return f"No hay facturas registradas en {mes}."

    total_ars = sum(float(r.get("monto", 0)) for r in facturas
                    if str(r.get("moneda", "")).lower() == "ars")
    total_usd = sum(float(r.get("monto", 0)) for r in facturas
                    if str(r.get("moneda", "")).lower() == "usd")
    pendiente = sum(float(r.get("monto", 0)) for r in facturas
                    if str(r.get("moneda", "")).lower() == "usd"
                    and str(r.get("estado", "")).lower() == "pendiente")

    lines = [f"📄 Facturas {mes}:\n"]
    for f in sorted(facturas, key=lambda r: str(r.get("fecha", "")), reverse=True):
        mon = "USD" if str(f.get("moneda", "")).lower() == "usd" else "$"
        estado = "✅" if str(f.get("estado", "")).lower() == "cobrado" else "⏳"
        lines.append(
            f"{estado} {f['cliente']} — {mon} {float(f.get('monto',0)):,.0f} — {f['concepto']}"
        )
    lines.append(f"\nTotal ARS: ${total_ars:,.0f}")
    lines.append(f"Total USD: USD {total_usd:,.0f}")
    if pendiente > 0:
        lines.append(f"⚠️ Pendiente cobro: USD {pendiente:,.0f}")
    return "\n".join(lines)


async def marcar_factura_cobrada(cliente: str, concepto: str = "") -> str:
    ws = WorksheetFacturas.get()
    rows = ws.get_all_values()
    for i, r in enumerate(rows[1:], start=2):
        if r[0].lower() == cliente.lower():
            if concepto and concepto.lower() not in str(r[4]).lower():
                continue
            ws.update(f"F{i}", "cobrado")
            return f"Factura de {r[0]} marcada como cobrada: {r[3]} {float(r[2]):,.0f}"
    return f"No se encontro factura pendiente de {cliente}."
