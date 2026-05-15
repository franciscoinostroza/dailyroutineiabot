from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.calendar import crear_evento as _crear_evento, leer_eventos as _leer_eventos, eliminar_evento as _eliminar_evento

tz = pytz.timezone(settings.timezone)

_ultimos_eventos_por_chat: dict[str, list[dict]] = {}


async def crear_evento_calendario(fecha: str, hora_inicio: str, hora_fin: str, titulo: str) -> str:
    inicio = f"{fecha}T{hora_inicio}:00"
    fin = f"{fecha}T{hora_fin}:00"
    _crear_evento(titulo, inicio, fin)
    return f"Evento creado: {titulo} — {fecha} {hora_inicio}-{hora_fin}"


async def ver_eventos_calendario(fecha: str = "hoy", chat_id: str = "") -> str:
    global _ultimos_eventos_por_chat
    arg_fecha = fecha.lower()
    hoy = datetime.now(tz).date()

    if arg_fecha == "hoy":
        fecha_dt = hoy
    elif arg_fecha in ("manana", "mañana"):
        fecha_dt = hoy + timedelta(days=1)
    else:
        try:
            fecha_dt = datetime.strptime(arg_fecha, "%Y-%m-%d").date()
        except ValueError:
            return f"Fecha invalida: {arg_fecha}. Usa YYYY-MM-DD, 'hoy' o 'manana'."

    dia_str = fecha_dt.strftime("%Y-%m-%d")
    try:
        eventos = _leer_eventos(dia_str)
        if chat_id:
            _ultimos_eventos_por_chat[chat_id] = eventos
        if not eventos:
            return f"No hay eventos para el {fecha_dt.strftime('%d/%m/%Y')}."
        lineas = [f"Eventos del {fecha_dt.strftime('%d/%m/%Y')}:"]
        for i, e in enumerate(eventos, 1):
            hora = e["start"].get("dateTime", e["start"].get("date", ""))
            hora = hora[11:16] if "T" in hora else "Todo el dia"
            lineas.append(f"  {i}. {hora} — {e.get('summary', 'Sin titulo')}")
        return "\n".join(lineas)
    except Exception as e:
        return f"Error al leer eventos: {e}"


async def eliminar_evento_calendario(indice: int, chat_id: str = "") -> str:
    global _ultimos_eventos_por_chat
    eventos = _ultimos_eventos_por_chat.get(chat_id, [])
    if not eventos:
        return "Primero consulta los eventos con ver_eventos_calendario."
    i = int(indice) - 1
    if i < 0 or i >= len(eventos):
        return f"Numero invalido. Hay {len(eventos)} eventos (usa 1 a {len(eventos)})."
    titulo = eventos[i].get("summary", "Sin titulo")
    try:
        _eliminar_evento(eventos[i]["id"])
        eventos.pop(i)
        return f"Evento eliminado: {titulo}"
    except Exception as e:
        return f"Error al eliminar: {e}"
