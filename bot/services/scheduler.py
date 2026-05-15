import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from bot.config import settings

DIA_MAP = {
    "lunes": "mon", "martes": "tue", "miercoles": "wed",
    "jueves": "thu", "viernes": "fri", "sabado": "sat", "domingo": "sun",
}


def programar_mensajes(scheduler: AsyncIOScheduler, bot, mensajes_dia: dict):
    import pytz
    tz = pytz.timezone(settings.timezone)
    for dia_es, mensajes in mensajes_dia.items():
        dia_en = DIA_MAP.get(dia_es)
        if not dia_en:
            continue
        for hora, minuto, texto in mensajes:
            scheduler.add_job(
                _enviar_mensaje,
                CronTrigger(day_of_week=dia_en, hour=hora, minute=minuto, timezone=tz),
                args=[bot, texto],
                id=f"rutina_{dia_es}_{hora}_{minuto}_{hash(texto) % 10000}",
                replace_existing=True,
            )


async def _enviar_mensaje(bot, texto: str):
    await bot.send_message(chat_id=settings.chat_id, text=texto)


def setup_scheduler(
    app: Application,
    mensajes_dia: dict,
    notificar_pagos_fn,
    notificar_recordatorios_fn,
    enviar_resumen_semanal_fn,
) -> AsyncIOScheduler:
    import pytz
    tz = pytz.timezone(settings.timezone)
    scheduler = AsyncIOScheduler()

    programar_mensajes(scheduler, app.bot, mensajes_dia)

    scheduler.add_job(
        notificar_pagos_fn,
        CronTrigger(hour=settings.notification_hour, minute=settings.notification_minute, timezone=tz),
        args=[app.bot],
        id="notificar_pagos",
    )
    scheduler.add_job(
        notificar_recordatorios_fn,
        CronTrigger(hour=settings.notification_hour, minute=settings.notification_minute, timezone=tz),
        args=[app.bot],
        id="notificar_recordatorios",
    )
    scheduler.add_job(
        enviar_resumen_semanal_fn,
        CronTrigger(
            day_of_week=settings.weekly_summary_day,
            hour=settings.weekly_summary_hour,
            minute=settings.weekly_summary_minute,
            timezone=tz,
        ),
        args=[app.bot],
        id="resumen_semanal",
    )

    scheduler.start()
    logging.info("Scheduler iniciado.")
    return scheduler
