from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import WorksheetRecordatorios

tz = pytz.timezone(settings.timezone)


async def agregar_recordatorio_puntual(texto: str) -> str:
    fecha = datetime.now(tz).strftime("%Y-%m-%d")
    WorksheetRecordatorios.append(texto, fecha)
    return f"Recordatorio agregado: {texto}"


async def ver_recordatorios_pendientes() -> str:
    pendientes = WorksheetRecordatorios.read_pending()
    if not pendientes:
        return "No hay recordatorios pendientes."
    lineas = ["Recordatorios pendientes:"]
    for i, r in enumerate(pendientes, 1):
        lineas.append(f"  {i}. {r['texto']} (desde {r.get('fecha_creacion', '?')})")
    return "\n".join(lineas)


async def marcar_recordatorio_hecho(indice: int) -> str:
    pendientes = WorksheetRecordatorios.read_pending()
    i = int(indice) - 1
    if i < 0 or i >= len(pendientes):
        return f"Numero invalido. Hay {len(pendientes)} pendientes (usa 1 a {len(pendientes)})."
    texto_buscado = str(pendientes[i]["texto"])
    fila = WorksheetRecordatorios.find_row_by_text(texto_buscado)
    if fila is None:
        return "No se pudo encontrar ese recordatorio."
    WorksheetRecordatorios.mark_done(fila)
    return f"Recordatorio marcado como hecho: {texto_buscado}"
