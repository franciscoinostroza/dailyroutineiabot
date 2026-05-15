import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet, get_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetPresupuestos:
    HEADERS = ["categoria", "presupuesto_mensual"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Presupuestos", WorksheetPresupuestos.HEADERS, rows=50, cols=5)

    @staticmethod
    def read_all() -> list[dict]:
        try:
            return WorksheetPresupuestos.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Presupuestos: {e}")
            return []

    @staticmethod
    def find_by_categoria(categoria: str) -> dict | None:
        for r in WorksheetPresupuestos.read_all():
            if str(r.get("categoria", "")).lower() == categoria.lower():
                return r
        return None

    @staticmethod
    def upsert(categoria: str, presupuesto: float):
        ws = WorksheetPresupuestos.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == categoria.lower():
                ws.update(f"B{i}", presupuesto)
                return
        ws.append_row([categoria, presupuesto])


async def agregar_presupuesto(categoria: str, monto: float) -> str:
    WorksheetPresupuestos.upsert(categoria, float(monto))
    return f"Presupuesto {categoria}: ${float(monto):,.0f}/mes"


async def ver_presupuesto() -> str:
    presupuestos = WorksheetPresupuestos.read_all()
    if not presupuestos:
        return "No hay presupuestos definidos. Usa agregar_presupuesto para crear uno."

    mes = datetime.now(tz).strftime("%Y-%m")

    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception:
        rows = []

    lineas = [f"📊 Presupuestos {mes}:\n"]

    for p in presupuestos:
        cat = str(p.get("categoria", ""))
        if not cat:
            continue
        presup = float(p.get("presupuesto_mensual", 0))
        gastado = sum(
            float(r.get("precio_final", 0))
            for r in rows
            if str(r.get("fecha", "")).startswith(mes)
            and cat.lower() in str(r.get("supermercado", "")).lower()
        )
        pct = (gastado / presup * 100) if presup > 0 else 0
        barra = _barra_progreso(pct)
        icono = "🟢" if pct < 70 else "🟡" if pct < 90 else "🔴"
        lineas.append(
            f"{icono} {cat}: ${gastado:,.0f} / ${presup:,.0f} {barra} ({pct:.0f}%)"
        )

    return "\n".join(lineas)


def _barra_progreso(pct: float, ancho: int = 10) -> str:
    lleno = min(int(pct / 100 * ancho), ancho)
    return f"[{'█' * lleno}{'░' * (ancho - lleno)}]"


async def verificar_alertas_presupuesto() -> list[str]:
    alertas = []
    presupuestos = WorksheetPresupuestos.read_all()
    if not presupuestos:
        return alertas

    mes = datetime.now(tz).strftime("%Y-%m")
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception:
        return alertas

    for p in presupuestos:
        cat = str(p.get("categoria", ""))
        if not cat:
            continue
        presup = float(p.get("presupuesto_mensual", 0))
        if presup <= 0:
            continue
        gastado = sum(
            float(r.get("precio_final", 0))
            for r in rows
            if str(r.get("fecha", "")).startswith(mes)
            and cat.lower() in str(r.get("supermercado", "")).lower()
        )
        pct = (gastado / presup * 100) if presup > 0 else 0
        if pct >= 80:
            alertas.append(
                f"⚠️ {cat}: ${gastado:,.0f} de ${presup:,.0f} ({pct:.0f}%)"
            )

    return alertas
