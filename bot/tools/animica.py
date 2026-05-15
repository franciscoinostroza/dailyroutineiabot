import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetAnimica:
    HEADERS = ["fecha", "estado", "nota"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Animica", WorksheetAnimica.HEADERS, rows=200, cols=5)

    @staticmethod
    def read_week() -> list[dict]:
        hoy = datetime.now(tz).date()
        inicio = hoy - timedelta(days=hoy.weekday())
        try:
            rows = WorksheetAnimica.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Animica: {e}")
            return []
        return [r for r in rows
                if str(r.get("fecha", "")) >= inicio.strftime("%Y-%m-%d")]

    @staticmethod
    def upsert(estado: str, nota: str = ""):
        from datetime import timedelta
        hoy = datetime.now(tz).strftime("%Y-%m-%d")
        ws = WorksheetAnimica.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0] == hoy:
                ws.update(f"B{i}", estado)
                if nota:
                    ws.update(f"C{i}", nota)
                return
        ws.append_row([hoy, estado, nota])

    @staticmethod
    def get_streak() -> str:
        from datetime import timedelta
        hoy = datetime.now(tz).date()
        rows = WorksheetAnimica.get().get_all_records()
        dias = {}
        for r in rows:
            try:
                d = r.get("fecha", "")
                e = r.get("estado", "")
                if d and e:
                    dias[d] = e
            except Exception:
                pass

        semana = []
        inicio = hoy - timedelta(days=hoy.weekday())
        for i in range(7):
            dia = (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
            estado = dias.get(dia, "?")
            if estado == "bien":
                icono = "😊"
            elif estado == "maso":
                icono = "😐"
            elif estado == "mal":
                icono = "😞"
            else:
                icono = "⬜"
            es_hoy = " ←" if dia == hoy.strftime("%Y-%m-%d") else ""
            semana.append(f"{icono} {dia[-5:]}{es_hoy}")

        counts = {"bien": 0, "maso": 0, "mal": 0}
        for e in dias.values():
            if e in counts:
                counts[e] += 1

        return "\n".join([
            "😌 Animica de la semana:\n",
            *semana,
            f"\nBien: {counts['bien']} | Maso: {counts['maso']} | Mal: {counts['mal']}"
        ])
