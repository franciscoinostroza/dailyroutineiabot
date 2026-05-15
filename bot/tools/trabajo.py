from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import WorksheetTrabajo

tz = pytz.timezone(settings.timezone)


def _cerrar_sesion_activa() -> str:
    row_idx, activa = WorksheetTrabajo.find_active_session()
    if activa is None:
        return ""
    ahora = datetime.now(tz).strftime("%H:%M")
    if row_idx:
        WorksheetTrabajo.update_cell(row_idx, "D", ahora)
        WorksheetTrabajo.update_cell(row_idx, "F", "terminado")
    proyecto = activa.get("proyecto", "")
    return f"(Se cerro sesion anterior: {proyecto}). "


async def iniciar_trabajo_tool(proyecto: str, descripcion: str = "") -> str:
    resultado = _cerrar_sesion_activa()
    ahora = datetime.now(tz)
    WorksheetTrabajo.append(
        ahora.strftime("%Y-%m-%d"), proyecto, ahora.strftime("%H:%M"), "", descripcion, "activo"
    )
    return resultado + f"Sesion iniciada: {proyecto} a las {ahora.strftime('%H:%M')}"


async def terminar_trabajo_tool() -> str:
    row_idx, activa = WorksheetTrabajo.find_active_session()
    if activa is None:
        return "No hay sesion activa."
    ahora = datetime.now(tz).strftime("%H:%M")
    if row_idx:
        WorksheetTrabajo.update_cell(row_idx, "D", ahora)
        WorksheetTrabajo.update_cell(row_idx, "F", "terminado")
    proyecto = activa.get("proyecto", "")
    return f"Sesion terminada: {proyecto} a las {ahora}"


def _calcular_horas(mes: str | None = None) -> tuple[float, list[dict], dict[str, float]]:
    if mes is None:
        mes = datetime.now(tz).strftime("%Y-%m")
    rows = WorksheetTrabajo.read_all()
    filas = [
        r for r in rows
        if str(r.get("fecha", "")).startswith(mes)
        and str(r.get("estado", "")).lower() == "terminado"
    ]
    total_min = 0.0
    por_proyecto: dict[str, float] = {}
    sesiones: list[dict] = []
    for r in filas:
        try:
            h_i = datetime.strptime(r["hora_inicio"], "%H:%M")
            h_f = datetime.strptime(r["hora_fin"], "%H:%M")
            mins = (h_f - h_i).seconds / 60.0
            total_min += mins
            proy = str(r.get("proyecto", "Sin proyecto"))
            por_proyecto[proy] = por_proyecto.get(proy, 0.0) + mins
            sesiones.append({**r, "minutos": mins})
        except Exception:
            pass
    return total_min / 60.0, sesiones, por_proyecto


async def ver_horas_trabajadas() -> str:
    horas, sesiones, por_proy = _calcular_horas()
    if horas == 0:
        return "No hay horas registradas este mes."
    lineas = [f"Horas trabajadas este mes: {horas:.1f}h total"]
    for proy, mins in por_proy.items():
        lineas.append(f"  {proy}: {mins / 60:.1f}h")
    return "\n".join(lineas)
