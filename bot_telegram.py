"""
BOT DE TELEGRAM - MI SISTEMA DE VIDA
=====================================
Requisitos:
  pip install python-telegram-bot==20.7 apscheduler pytz gspread google-auth

Configuración:
  1. Hablá con @BotFather en Telegram y creá un bot → te da un TOKEN
  2. Hablá con @userinfobot para obtener tu CHAT_ID
  3. Completá el archivo .env con TOKEN, CHAT_ID, OPENAI_KEY, SHEET_ID, CREDENTIALS_FILE
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
import gspread
from google.oauth2.service_account import Credentials
import pytz
import asyncio

load_dotenv()

# ─── CONFIGURACIÓN ───────────────────────────────────────────────
TOKEN            = os.getenv("TOKEN")
CHAT_ID          = os.getenv("CHAT_ID")
TIMEZONE         = os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires")
SHEET_ID         = os.getenv("SHEET_ID")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
openai_client    = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
tz = pytz.timezone(TIMEZONE)

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# Datos de agenda (se cargan desde Google Sheets)
MENSAJES_DIA: dict = {}
RESUMEN: dict = {}


def cargar_agenda():
    global MENSAJES_DIA, RESUMEN
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(SHEET_ID).sheet1
        rows = ws.get_all_records()

        mensajes: dict = {}
        for row in rows:
            dia    = str(row["dia"]).strip().lower()
            hora   = int(row["hora"])
            minuto = int(row["minuto"])
            msg    = str(row["mensaje"])
            mensajes.setdefault(dia, []).append((hora, minuto, msg))

        resumen: dict = {}
        for dia, lista in mensajes.items():
            for h, m, txt in lista:
                if h == 6 and m == 0:
                    resumen[dia] = txt
                    break

        MENSAJES_DIA = mensajes
        RESUMEN = resumen
        total = sum(len(v) for v in mensajes.values())
        logging.info(f"Agenda cargada desde Sheet: {total} mensajes en {len(mensajes)} días.")
        return True
    except Exception as e:
        logging.error(f"Error cargando agenda desde Sheet: {e}")
        return False


# ─── HANDLERS ────────────────────────────────────────────────────
async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    dia = datetime.now(tz).strftime("%A").lower()
    dia_es = DIAS_SEMANA[["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].index(dia)]
    await update.message.reply_text(RESUMEN.get(dia_es, "No hay resumen para hoy."))

async def recargar(update, context: ContextTypes.DEFAULT_TYPE):
    ok = cargar_agenda()
    if ok:
        await update.message.reply_text(
            "✅ Agenda recargada desde Google Sheets.\n"
            "Nota: los mensajes automáticos programados requieren reiniciar el bot para actualizarse."
        )
    else:
        await update.message.reply_text("❌ Error al recargar la agenda. Revisá los logs.")

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "👋 Hola Francisco! Soy tu asistente personal de rutina diaria.\n\n"
        "Esto es lo que puedo hacer por vos:\n\n"
        "📅 Recordatorios automáticos — Te aviso a cada hora del día según tu agenda semanal.\n\n"
        "🤖 Asistente con IA — Escribime cualquier cosa y te respondo en base a tu rutina. Por ejemplo:\n"
        "  • ¿Qué debería estar haciendo ahora?\n"
        "  • ¿Qué como hoy?\n"
        "  • ¿Qué me falta hacer?\n\n"
        "📋 Comandos disponibles:\n"
        "/hoy — Ver el resumen del día\n"
        "/recargar — Recargar la agenda desde Google Sheets\n"
        "/test — Verificar que el bot funciona\n"
        "/ayuda — Ver esta ayuda\n"
    )
    await update.message.reply_text(texto)

async def test(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando y los mensajes automáticos están activos.")

async def ayuda(update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "Bot - Mi Sistema de Vida\n\n"
        "Comandos disponibles:\n"
        "/hoy — Ver el resumen del día\n"
        "/recargar — Recargar agenda desde Google Sheets\n"
        "/ayuda — Ver esta ayuda\n\n"
        "El bot te avisa automáticamente en cada horario del día."
    )
    await update.message.reply_text(texto)


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
    await bot.send_message(chat_id=CHAT_ID, text=texto)

def programar_mensajes(scheduler, bot):
    dia_map = {
        "lunes": "mon", "martes": "tue", "miercoles": "wed",
        "jueves": "thu", "viernes": "fri", "sabado": "sat", "domingo": "sun"
    }
    for dia_es, mensajes in MENSAJES_DIA.items():
        dia_en = dia_map.get(dia_es)
        if not dia_en:
            continue
        for hora, minuto, texto in mensajes:
            scheduler.add_job(
                enviar_mensaje,
                CronTrigger(day_of_week=dia_en, hour=hora, minute=minuto, timezone=tz),
                args=[bot, texto],
                id=f"{dia_es}_{hora}_{minuto}"
            )


# ─── MAIN ────────────────────────────────────────────────────────
async def main():
    cargar_agenda()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hoy", hoy))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("recargar", recargar))
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
