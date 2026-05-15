import logging
import asyncio
from datetime import datetime
import pytz

from bot.config import settings
from bot.tools.briefing import generar_briefing
from bot.tools.deadlines import ver_deadlines
from bot.tools.trabajo import _calcular_horas

tz = pytz.timezone(settings.timezone)


async def _preguntar_standup(bot) -> str | None:
    """Envia pregunta de standup y espera respuesta. Retorna la respuesta o None."""
    try:
        msg = await bot.send_message(
            chat_id=settings.chat_id,
            text="🌅 Buenos dias Francisco! Antes del briefing:\n"
                 "¿En que vas a trabajar hoy? ¿Algo trabado o que necesites?"
        )
        return None
    except Exception as e:
        logging.error(f"Error en standup pregunta: {e}")
        return None


async def enviar_standup(bot) -> None:
    try:
        await _preguntar_standup(bot)
    except Exception as e:
        logging.error(f"Error en standup: {e}", exc_info=True)
