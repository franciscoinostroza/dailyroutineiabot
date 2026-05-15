import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.auth import get_calendar_service

tz = pytz.timezone(settings.timezone)


def _build_event_body(titulo: str, inicio: str, fin: str, descripcion: str = "") -> dict:
    return {
        "summary": titulo,
        "description": descripcion,
        "start": {"dateTime": inicio, "timeZone": settings.timezone},
        "end": {"dateTime": fin, "timeZone": settings.timezone},
    }


def crear_evento(titulo: str, inicio: str, fin: str, descripcion: str = "") -> dict:
    service = get_calendar_service()
    evento = _build_event_body(titulo, inicio, fin, descripcion)
    logging.info(f"Creando evento en calendario {settings.calendar_id}: {titulo} {inicio}-{fin}")
    resultado = service.events().insert(calendarId=settings.calendar_id, body=evento).execute()
    logging.info(f"Evento creado OK: {resultado.get('id')}")
    return resultado


def leer_eventos(dia_str: str) -> list[dict]:
    from datetime import timedelta
    fecha = datetime.strptime(dia_str, "%Y-%m-%d")
    inicio = tz.localize(fecha.replace(hour=0, minute=0, second=0))
    fin = tz.localize(fecha.replace(hour=23, minute=59, second=59))
    service = get_calendar_service()
    resultado = service.events().list(
        calendarId=settings.calendar_id,
        timeMin=inicio.isoformat(),
        timeMax=fin.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return resultado.get("items", [])


def eliminar_evento(evento_id: str):
    service = get_calendar_service()
    service.events().delete(
        calendarId=settings.calendar_id,
        eventId=evento_id,
    ).execute()
