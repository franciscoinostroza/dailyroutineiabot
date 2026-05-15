import logging
from bot.config import settings
from bot.services.auth import get_gc
from tenacity import retry, stop_after_attempt, wait_exponential

import gspread


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_worksheet(name: str = "Agenda"):
    return get_gc().open_by_key(settings.sheet_id).worksheet(name)


def get_or_create_worksheet(name: str, headers: list[str], rows: int = 100, cols: int = 10):
    gc = get_gc()
    sh = gc.open_by_key(settings.sheet_id)
    try:
        ws = sh.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(name, rows=rows, cols=cols)
        ws.append_row(headers)
        logging.info(f"Hoja '{name}' creada automaticamente.")
    return ws


class WorksheetPagos:
    HEADERS = ["nombre", "monto", "dia_vencimiento", "categoria", "activo", "ultimo_mes"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Pagos", WorksheetPagos.HEADERS)

    @staticmethod
    def read_all(solo_activos: bool = True) -> list[dict]:
        try:
            rows = WorksheetPagos.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Pagos: {e}")
            return []
        if solo_activos:
            rows = [r for r in rows if str(r.get("activo", "si")).lower() != "no"]
        return rows

    @staticmethod
    def append(nombre: str, monto: float, dia_venc: int, categoria: str = ""):
        WorksheetPagos.get().append_row([nombre, monto, dia_venc, categoria, "si", ""])

    @staticmethod
    def find_row(nombre: str) -> int | None:
        ws = WorksheetPagos.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == nombre.lower():
                return i
        return None

    @staticmethod
    def mark_paid(row: int, mes: str):
        ws = WorksheetPagos.get()
        ws.update(f"F{row}", mes)

    @staticmethod
    def delete_row(row: int):
        WorksheetPagos.get().delete_rows(row)


class WorksheetTrabajo:
    HEADERS = ["fecha", "proyecto", "hora_inicio", "hora_fin", "descripcion", "estado"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Trabajo", WorksheetTrabajo.HEADERS, rows=200, cols=10)

    @staticmethod
    def read_all() -> list[dict]:
        try:
            return WorksheetTrabajo.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Trabajo: {e}")
            return []

    @staticmethod
    def append(fecha: str, proyecto: str, hora_inicio: str, hora_fin: str = "",
               descripcion: str = "", estado: str = "activo"):
        WorksheetTrabajo.get().append_row([fecha, proyecto, hora_inicio, hora_fin, descripcion, estado])

    @staticmethod
    def find_active_session() -> tuple[int | None, dict | None]:
        rows = WorksheetTrabajo.read_all()
        for i, r in enumerate(reversed(rows), start=1):
            if str(r.get("estado", "")).lower() == "activo":
                row_index = len(rows) - i + 2
                return row_index, r
        return None, None

    @staticmethod
    def update_cell(row: int, col: str, value: str):
        ws = WorksheetTrabajo.get()
        ws.update(f"{col}{row}", value)


class WorksheetRecordatorios:
    HEADERS = ["texto", "fecha_creacion", "estado"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Recordatorios", WorksheetRecordatorios.HEADERS, rows=100, cols=5)

    @staticmethod
    def read_pending() -> list[dict]:
        try:
            rows = WorksheetRecordatorios.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Recordatorios: {e}")
            return []
        return [r for r in rows if str(r.get("estado", "")).lower() != "hecho"]

    @staticmethod
    def append(texto: str, fecha: str, estado: str = "pendiente"):
        WorksheetRecordatorios.get().append_row([texto, fecha, estado])

    @staticmethod
    def find_row_by_text(texto: str, pendiente_only: bool = True) -> int | None:
        ws = WorksheetRecordatorios.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if str(r[0]) == str(texto):
                if pendiente_only and str(r[2]).lower() == "hecho":
                    continue
                return i
        return None

    @staticmethod
    def mark_done(row: int):
        ws = WorksheetRecordatorios.get()
        ws.update(f"C{row}", "hecho")
