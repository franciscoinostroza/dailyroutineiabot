import logging
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetDeadlines:
    HEADERS = ["proyecto", "fecha_entrega", "dias_habiles_restantes", "estado", "notas"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Deadlines", WorksheetDeadlines.HEADERS, rows=100, cols=8)

    @staticmethod
    def read_all() -> list[dict]:
        try:
            return WorksheetDeadlines.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Deadlines: {e}")
            return []

    @staticmethod
    def read_active() -> list[dict]:
        return [d for d in WorksheetDeadlines.read_all()
                if str(d.get("estado", "")).lower() != "entregado"]

    @staticmethod
    def upsert(proyecto: str, fecha_entrega: str, notas: str = ""):
        ws = WorksheetDeadlines.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == proyecto.lower():
                ws.update(f"B{i}", fecha_entrega)
                ws.update(f"E{i}", notas)
                return
        dias_hab = _calcular_dias_habiles(fecha_entrega)
        ws.append_row([proyecto, fecha_entrega, dias_hab, "pendiente", notas])

    @staticmethod
    def mark_delivered(proyecto: str):
        ws = WorksheetDeadlines.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == proyecto.lower():
                ws.update(f"D{i}", "entregado")

    @staticmethod
    def delete_row(proyecto: str):
        ws = WorksheetDeadlines.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == proyecto.lower():
                ws.delete_rows(i)
                return


def _calcular_dias_habiles(fecha_str: str) -> int:
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = datetime.now(tz).date()
        dias = 0
        dia = hoy
        while dia <= fecha:
            if dia.weekday() < 5:
                dias += 1
            dia += timedelta(days=1)
        return dias
    except Exception:
        return 0


async def agregar_deadline(proyecto: str, fecha_entrega: str, notas: str = "") -> str:
    dias = _calcular_dias_habiles(fecha_entrega)
    WorksheetDeadlines.upsert(proyecto, fecha_entrega, notas)
    return f"Deadline: {proyecto} — {fecha_entrega} ({dias} dias habiles restantes)"


async def ver_deadlines() -> str:
    deadlines = WorksheetDeadlines.read_active()
    if not deadlines:
        return "No hay deadlines activos. Agrega uno con /deadline agregar."

    lines = ["📅 Deadlines activos:\n"]
    for d in deadlines:
        fecha = str(d.get("fecha_entrega", ""))
        try:
            dias_hab = _calcular_dias_habiles(fecha)
        except Exception:
            dias_hab = 0
        icono = "🔴" if dias_hab <= 1 else "🟡" if dias_hab <= 3 else "🟢"
        lines.append(f"{icono} {d['proyecto']} — {fecha} ({dias_hab}d habiles)")
    return "\n".join(lines)


async def verificar_deadlines(bot) -> None:
    deadlines = WorksheetDeadlines.read_active()
    if not deadlines:
        return

    alertas = []
    for d in deadlines:
        fecha = str(d.get("fecha_entrega", ""))
        try:
            dias_hab = _calcular_dias_habiles(fecha)
        except Exception:
            continue
        if dias_hab <= 1:
            alertas.append(f"🔴 HOY: {d['proyecto']}")
        elif dias_hab <= 3:
            alertas.append(f"🟡 {dias_hab}d habiles: {d['proyecto']}")

    if alertas:
        msg = "⚠️ Alertas de deadlines:\n\n" + "\n".join(alertas)
        try:
            await bot.send_message(chat_id=settings.chat_id, text=msg)
        except Exception as e:
            logging.error(f"Error enviando alerta de deadline: {e}")
