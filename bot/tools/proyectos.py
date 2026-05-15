import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetProyectos:
    HEADERS = ["nombre", "descripcion", "stack", "repo_url", "cliente", "fecha_inicio", "estado"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Proyectos", WorksheetProyectos.HEADERS, rows=100, cols=10)

    @staticmethod
    def read_all() -> list[dict]:
        try:
            return WorksheetProyectos.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Proyectos: {e}")
            return []

    @staticmethod
    def find_by_nombre(nombre: str) -> tuple[int | None, dict | None]:
        ws = WorksheetProyectos.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == nombre.lower():
                records = WorksheetProyectos.read_all()
                return i, records[i - 2] if i - 2 < len(records) else None
        return None, None

    @staticmethod
    def upsert(nombre: str, descripcion: str = "", stack: str = "",
               repo_url: str = "", cliente: str = "", estado: str = "activo"):
        row_idx, existing = WorksheetProyectos.find_by_nombre(nombre)
        ws = WorksheetProyectos.get()
        if row_idx and existing:
            if descripcion:
                ws.update(f"B{row_idx}", descripcion)
            if stack:
                ws.update(f"C{row_idx}", stack)
            if repo_url:
                ws.update(f"D{row_idx}", repo_url)
            if cliente:
                ws.update(f"E{row_idx}", cliente)
            if estado:
                ws.update(f"G{row_idx}", estado)
        else:
            ws.append_row([nombre, descripcion, stack, repo_url, cliente,
                          datetime.now(tz).strftime("%Y-%m-%d"), estado])
            logging.info(f"Proyecto creado: {nombre}")


class WorksheetDocumentacion:
    HEADERS = ["proyecto", "tipo", "contenido", "fecha_actualizacion"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Documentacion", WorksheetDocumentacion.HEADERS, rows=200, cols=10)

    @staticmethod
    def read_by_proyecto(proyecto: str, tipo: str | None = None) -> list[dict]:
        try:
            rows = WorksheetDocumentacion.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Documentacion: {e}")
            return []
        result = [r for r in rows if str(r.get("proyecto", "")).lower() == proyecto.lower()]
        if tipo:
            result = [r for r in result if str(r.get("tipo", "")).lower() == tipo.lower()]
        return result

    @staticmethod
    def upsert(proyecto: str, tipo: str, contenido: str):
        ws = WorksheetDocumentacion.get()
        rows = ws.get_all_values()
        for i, r in enumerate(rows[1:], start=2):
            if r[0].lower() == proyecto.lower() and r[1].lower() == tipo.lower():
                ws.update(f"C{i}", contenido)
                ws.update(f"D{i}", datetime.now(tz).strftime("%Y-%m-%d"))
                return
        ws.append_row([proyecto, tipo, contenido, datetime.now(tz).strftime("%Y-%m-%d")])

    @staticmethod
    def append_changelog(proyecto: str, entrada: str):
        existing = WorksheetDocumentacion.read_by_proyecto(proyecto, "changelog")
        if existing:
            contenido = str(existing[0].get("contenido", ""))
            fecha = datetime.now(tz).strftime("%Y-%m-%d")
            contenido = f"## {fecha}\n- {entrada}\n\n{contenido}"
            WorksheetDocumentacion.upsert(proyecto, "changelog", contenido)
        else:
            WorksheetDocumentacion.upsert(proyecto, "changelog",
                f"## {datetime.now(tz).strftime('%Y-%m-%d')}\n- {entrada}\n")


async def add_new_project(nombre: str, descripcion: str = "") -> str:
    nombre = nombre.strip()
    if not nombre:
        return "El nombre del proyecto no puede estar vacio."
    WorksheetProyectos.upsert(nombre, descripcion, estado="activo")
    return f"Proyecto creado: {nombre}. Podes pedirme que genere documentacion con /proyecto readme {nombre}"


async def view_project_info(nombre: str) -> str:
    _, p = WorksheetProyectos.find_by_nombre(nombre)
    if p is None:
        return f"Proyecto '{nombre}' no encontrado."
    from bot.tools.trabajo import _calcular_horas
    horas, sesiones, por_proy = _calcular_horas()
    horas_proy = por_proy.get(nombre, 0) / 60
    docs = WorksheetDocumentacion.read_by_proyecto(nombre)
    tipos = ", ".join(set(d.get("tipo", "") for d in docs)) if docs else "sin docs"
    return (
        f"Proyecto: {p['nombre']} | {p.get('descripcion','')} | "
        f"Stack: {p.get('stack','-')} | Cliente: {p.get('cliente','-')} | "
        f"Horas mes: {horas_proy:.1f}h | Docs: {tipos}"
    )


async def generate_documentation(proyecto: str, tipo: str, extra: str = "") -> str:
    return "Usa /proyecto readme|deploy|api|cliente <nombre> para generar documentacion."

