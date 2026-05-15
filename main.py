import asyncio
import logging
import os

from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from bot.config import settings
from bot.tools.rutina import cargar_agenda, MENSAJES_DIA
from bot.tools.resumen import notificar_pagos, notificar_recordatorios, enviar_resumen_semanal
from bot.services.scheduler import setup_scheduler
from bot.services.health import start_health_server, stop_health_server

from bot.handlers.basics import start, ayuda, test
from bot.handlers.agenda import hoy, listar, recargar, agregar, borrar
from bot.handlers.compras import compra, donde, descuentos, gastos, historial_cmd
from bot.handlers.calendario import agenda_calendar, eliminar_evento_cmd, evento
from bot.handlers.pagos import pago, pagos_proximos_cmd
from bot.handlers.callbacks import callback_botones
from bot.handlers.ia_chat import responder_ia
from bot.handlers.presupuestos import presupuesto
from bot.handlers.exportar import estadisticas, exportar


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    ok, err = cargar_agenda()
    if not ok:
        logging.warning(
            f"No se pudo cargar la agenda al inicio: {err}. "
            "Verifica GOOGLE_CREDENTIALS en las variables de entorno."
        )

    app = Application.builder().token(settings.token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("hoy", hoy))
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("agregar", agregar))
    app.add_handler(CommandHandler("borrar", borrar))
    app.add_handler(CommandHandler("recargar", recargar))
    app.add_handler(CommandHandler("compra", compra))
    app.add_handler(CommandHandler("donde", donde))
    app.add_handler(CommandHandler("descuentos", descuentos))
    app.add_handler(CommandHandler("gastos", gastos))
    app.add_handler(CommandHandler("evento", evento))
    app.add_handler(CommandHandler("agenda", agenda_calendar))
    app.add_handler(CommandHandler("eliminar_evento", eliminar_evento_cmd))
    app.add_handler(CallbackQueryHandler(callback_botones))
    app.add_handler(CommandHandler("historial", historial_cmd))
    app.add_handler(CommandHandler("pago", pago))
    app.add_handler(CommandHandler("pagos", pagos_proximos_cmd))
    app.add_handler(CommandHandler("presupuesto", presupuesto))
    app.add_handler(CommandHandler("estadisticas", estadisticas))
    app.add_handler(CommandHandler("exportar", exportar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_ia))

    scheduler = setup_scheduler(
        app, MENSAJES_DIA,
        notificar_pagos, notificar_recordatorios, enviar_resumen_semanal,
    )

    health_port = int(os.environ.get("HEALTH_PORT", "0"))
    if health_port > 0:
        start_health_server(health_port)

    logging.info("✅ Bot iniciado.")
    try:
        async with app:
            await app.start()
            await app.updater.start_polling()
            await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        stop_health_server()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
