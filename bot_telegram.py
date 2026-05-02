"""
BOT DE TELEGRAM - MI SISTEMA DE VIDA
=====================================
Requisitos:
  pip install python-telegram-bot==20.7 apscheduler pytz

Configuración:
  1. Hablá con @BotFather en Telegram y creá un bot → te da un TOKEN
  2. Hablá con @userinfobot para obtener tu CHAT_ID
  3. Reemplazá TOKEN y CHAT_ID abajo
  4. Ejecutá: python bot.py
"""

import logging
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from openai import AsyncOpenAI
import pytz
import asyncio

load_dotenv()

# ─── CONFIGURACIÓN ───────────────────────────────────────────────
TOKEN    = os.getenv("TOKEN")
CHAT_ID  = os.getenv("CHAT_ID")
TIMEZONE = os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires")
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
tz = pytz.timezone(TIMEZONE)

# ─── HORARIOS POR DÍA ────────────────────────────────────────────
HORARIOS = {
    # (hora, minuto): "mensaje"
    # Aplica lunes a domingo salvo se indique
}

MENSAJES_DIA = {
    "lunes": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Lunes</b>\n"
            "🧹 Limpieza: Baño completo (9:15)\n"
            "🍽 Almuerzo: Arroz con pollo\n"
            "💼 Trabajo: 14:00 – 18:00\n"
            "🗑 Recordatorio: tirar la basura después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> Baño completo (20 min). ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura</b> hoy."),
    ],
    "martes": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Martes</b>\n"
            "🧹 Limpieza: Barrer y trapear planta baja (9:15)\n"
            "🍽 Almuerzo: Tarta de pollo\n"
            "💼 Trabajo: 14:00 – 18:00\n"
            "🗑 Recordatorio: tirar la basura después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> Barrer y trapear planta baja (20 min). ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura</b> hoy."),
    ],
    "miercoles": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Miércoles</b>\n"
            "🧹 Limpieza: 2do piso — ordenar, cama y piso (9:15)\n"
            "🍽 Almuerzo: Pastas con salsa\n"
            "💼 Trabajo: 14:00 – 18:00\n"
            "🗑 Recordatorio: tirar la basura después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> 2do piso — ordenar, hacer la cama, limpiar piso (20 min). ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura</b> hoy."),
    ],
    "jueves": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Jueves</b>\n"
            "🧹 Limpieza: Ordenar objetos generales (9:15)\n"
            "🍽 Almuerzo: Pata y muslo al horno con papas\n"
            "💼 Trabajo: 14:00 – 18:00\n"
            "🗑 Recordatorio: tirar basura Y reciclaje después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> Ordenar objetos generales (15 min). ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura Y el reciclaje</b> hoy."),
    ],
    "viernes": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Viernes</b>\n"
            "🧹 Limpieza: Barrer y trapear (repaso, 9:15)\n"
            "🍽 Almuerzo: Milanesas de pollo con puré\n"
            "💼 Trabajo: 14:00 – 17:00\n"
            "⛪ Grupo iglesia: 17:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> Barrer y trapear (repaso, 20 min). ¡Arrancá!"),
    ],
    "sabado": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Sábado</b>\n"
            "🧹 Limpieza: 2do piso (9:15)\n"
            "🍽 Almuerzo: Libre\n"
            "💼 Trabajo: 14:00 – 17:00\n"
            "⛪ Iglesia: 17:00\n"
            "🗑 Recordatorio: basura Y reciclaje después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> 2do piso (20 min). ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura Y el reciclaje</b> hoy."),
    ],
    "domingo": [
        (6, 0,
            "☀️ <b>Buenos días, Francisco!</b>\n\n"
            "📋 <b>Tu día de hoy — Domingo</b>\n"
            "🧹 Limpieza: Antes de salir (9:15)\n"
            "⛪ Iglesia: 10:00 — enlistarse a las 9:50\n"
            "🍽 Almuerzo libre al volver\n"
            "🗑 Recordatorio: tirar la basura después de las 20:00"
        ),
        (9, 15, "🧹 <b>Limpieza del día:</b> Ordenar antes de salir. ¡Arrancá!"),
        (20, 0, "🗑 Acordate de <b>tirar la basura</b> hoy."),
    ],
}

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# ─── RESUMEN DEL DÍA ─────────────────────────────────────────────
RESUMEN = {
    "lunes":     "📋 <b>Hoy es LUNES</b>\n🧹 Limpieza: Baño completo (9:15)\n🍽 Almuerzo: Arroz con pollo\n💼 Trabajo: 14:00 – 18:00\n🗑 Basura después de las 20:00",
    "martes":    "📋 <b>Hoy es MARTES</b>\n🧹 Limpieza: Barrer y trapear planta baja (9:15)\n🍽 Almuerzo: Tarta de pollo\n💼 Trabajo: 14:00 – 18:00\n🗑 Basura después de las 20:00",
    "miercoles": "📋 <b>Hoy es MIÉRCOLES</b>\n🧹 Limpieza: 2do piso (9:15)\n🍽 Almuerzo: Pastas con salsa\n💼 Trabajo: 14:00 – 18:00\n🗑 Basura después de las 20:00",
    "jueves":    "📋 <b>Hoy es JUEVES</b>\n🧹 Limpieza: Ordenar objetos generales (9:15)\n🍽 Almuerzo: Pata y muslo al horno con papas\n💼 Trabajo: 14:00 – 18:00\n🗑 Basura Y reciclaje después de las 20:00",
    "viernes":   "📋 <b>Hoy es VIERNES</b>\n🧹 Limpieza: Barrer y trapear (repaso, 9:15)\n🍽 Almuerzo: Milanesas de pollo con puré\n💼 Trabajo: 14:00 – 17:00\n⛪ Grupo iglesia: 17:00",
    "sabado":    "📋 <b>Hoy es SÁBADO</b>\n🧹 Limpieza: 2do piso (9:15)\n🍽 Almuerzo: Libre\n💼 Trabajo: 14:00 – 17:00\n⛪ Iglesia: 17:00\n🗑 Basura Y reciclaje después de las 20:00",
    "domingo":   "📋 <b>Hoy es DOMINGO</b>\n🧹 Limpieza: Antes de salir (9:15)\n⛪ Iglesia: 10:00 (salir 9:50)\n🍽 Almuerzo libre al volver\n🗑 Basura después de las 20:00",
}

# ─── HANDLERS ────────────────────────────────────────────────────
async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    dia = datetime.now(tz).strftime("%A").lower()
    dia_es = DIAS_SEMANA[["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].index(dia)]
    await update.message.reply_text(RESUMEN.get(dia_es, "No hay resumen para hoy."), parse_mode="HTML")

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "👋 <b>Hola Francisco!</b> Soy tu asistente personal de rutina diaria.\n\n"
        "Esto es lo que puedo hacer por vos:\n\n"
        "📅 <b>Recordatorios automáticos</b> — Te aviso a cada hora del día según tu agenda semanal.\n\n"
        "🤖 <b>Asistente con IA</b> — Escribime cualquier cosa y te respondo en base a tu rutina. Por ejemplo:\n"
        "  • <i>¿Qué debería estar haciendo ahora?</i>\n"
        "  • <i>¿Qué como hoy?</i>\n"
        "  • <i>¿Qué me falta hacer?</i>\n\n"
        "📋 <b>Comandos disponibles:</b>\n"
        "/hoy — Ver el resumen del día\n"
        "/test — Verificar que el bot funciona\n"
        "/ayuda — Ver esta ayuda\n"
    )
    await update.message.reply_text(texto, parse_mode="HTML")

async def test(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando y los mensajes automáticos están activos.")

async def ayuda(update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        " <b>Bot - Mi Sistema de Vida</b>\n\n"
        "Comandos disponibles:\n"
        "/hoy — Ver el resumen del día\n"
        "/ayuda — Ver esta ayuda\n\n"
        "El bot te avisa automáticamente en cada horario del día "
    )
    await update.message.reply_text(texto, parse_mode="HTML")

# ─── IA: RESPUESTA A MENSAJES LIBRES ─────────────────────────────
def _build_system_prompt():
    from datetime import datetime
    ahora = datetime.now(tz)
    dia = ahora.strftime("%A").lower()
    dia_es = DIAS_SEMANA[["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].index(dia)]
    hora_actual = ahora.strftime("%H:%M")

    agenda_completa = ""
    for d in DIAS_SEMANA:
        mensajes = "\n".join(
            f"    {h:02d}:{m:02d} — {txt}" for h, m, txt in MENSAJES_DIA.get(d, [])
        )
        agenda_completa += f"\n{d.upper()}:\n{mensajes}\n"

    return (
        "Sos el asistente personal de Francisco. Conocés toda su agenda semanal y lo ayudás a seguirla.\n"
        "Cuando te dirijas a él, llamalo Francisco (no 'amigo', no 'usuario').\n\n"
        f"HOY ES {dia_es.upper()} Y LA HORA ACTUAL ES {hora_actual}.\n\n"
        f"MI AGENDA COMPLETA:\n{agenda_completa}\n"
        "Cuando te pregunte algo, respondé siempre en base a MI agenda real y en español.\n"
        "Sé cercano, cálido y natural — como un amigo que me conoce bien. No seas cortante ni frío.\n"
        "Evitá respuestas de una sola línea o frases sueltas como 'disfrutalo' sin nada más.\n"
        "Si me despido (chau, hasta luego, buenas noches, nos vemos, etc.), despedite vos también de forma cálida y natural.\n"
        "No inventes horarios ni actividades que no estén en mi agenda.\n"
        "IMPORTANTE: No uses markdown. No uses asteriscos (*), almohadillas (#) ni ningún símbolo de formato. Escribí texto plano y natural."
    )

historial = []
MAX_HISTORIAL = 30

async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    historial.append({"role": "user", "content": texto})
    if len(historial) > MAX_HISTORIAL:
        del historial[:-MAX_HISTORIAL]
    await update.message.chat.send_action("typing")
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                *historial
            ],
            max_tokens=500,
        )
        respuesta = response.choices[0].message.content
        historial.append({"role": "assistant", "content": respuesta})
        if len(historial) > MAX_HISTORIAL:
            del historial[:-MAX_HISTORIAL]
    except Exception as e:
        respuesta = f"Error al consultar la IA: {e}"
    await update.message.reply_text(respuesta)

# ─── ENVÍO PROGRAMADO ────────────────────────────────────────────
async def enviar_mensaje(bot, texto):
    historial.append({"role": "assistant", "content": texto})
    if len(historial) > MAX_HISTORIAL:
        del historial[:-MAX_HISTORIAL]
    await bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode="HTML")

def programar_mensajes(scheduler, bot):
    dia_map = {
        "lunes": "mon", "martes": "tue", "miercoles": "wed",
        "jueves": "thu", "viernes": "fri", "sabado": "sat", "domingo": "sun"
    }
    for dia_es, mensajes in MENSAJES_DIA.items():
        dia_en = dia_map[dia_es]
        for hora, minuto, texto in mensajes:
            scheduler.add_job(
                enviar_mensaje,
                CronTrigger(day_of_week=dia_en, hour=hora, minute=minuto, timezone=tz),
                args=[bot, texto],
                id=f"{dia_es}_{hora}_{minuto}"
            )

# ─── MAIN ────────────────────────────────────────────────────────
async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoy", hoy))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_ia))

    scheduler = AsyncIOScheduler()
    programar_mensajes(scheduler, app.bot)
    scheduler.start()

    print("✅ Bot iniciado. Esperando mensajes...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())

