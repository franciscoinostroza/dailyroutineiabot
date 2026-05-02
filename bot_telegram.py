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
    "lunes":    [
        (6,  0,  "☀️ <b>Buenos días!</b> Hora del devocional. Que sea un buen comienzo."),
        (6, 45,  " Devocional terminado. Ahora 45 min de aprendizaje libre."),
        (8,  0,  " Hora de preparar el desayuno. Listo antes de las 9:00."),
        (9,  0,  "️ Platos y limpiar la mesa del desayuno."),
        (9, 15,  " <b>Limpieza del día:</b> Baño completo (20 min)."),
        (10, 0,  " Hora del parque con la familia. Disfrutá el sol!"),
        (12, 0,  " De vuelta a casa. Si quedó limpieza pendiente, ahora es el momento."),
        (12,30,  " Almuerzo: Arroz con pollo. Acordate de limpiar la mesa y los platos."),
        (14, 0,  " <b>Bloque de trabajo.</b> Revisá tus tareas pendientes y arrancá."),
        (16, 0,  "☕ Pausa de 15 min. Estirá las piernas."),
        (16,15,  " Continuá con el proyecto o buscá trabajos nuevos en Workana."),
        (17,30,  " Respondé mensajes y cerrá el día de trabajo."),
        (18, 0,  " Tiempo con el bebé. Dejá el trabajo para después."),
        (20, 0,  "️ Cena. No olvidés tirar la basura después de las 20:00."),
        (20,30,  " Tiempo familiar: lectura y oración. Buenas noches familia!"),
        (22, 0,  " Hora de descansar. Revisá si hay pan para mañana antes de dormir."),
    ],
    "martes":   [
        (6,  0,  "☀️ <b>Buenos días!</b> Hora del devocional."),
        (6, 45,  " Aprendizaje libre hasta las 8:00."),
        (8,  0,  " A preparar el desayuno."),
        (9,  0,  "️ Platos y mesa limpia."),
        (9, 15,  " <b>Limpieza del día:</b> Barrer y trapear planta baja (20 min)."),
        (10, 0,  " Parque con la familia!"),
        (12,30,  " Almuerzo: Tarta de pollo (resto del lunes)."),
        (14, 0,  " <b>Bloque de trabajo.</b> Arrancá con lo más importante."),
        (16, 0,  "☕ Pausa corta."),
        (16,15,  " Seguí con proyectos o Workana."),
        (18, 0,  " Tiempo con el bebé."),
        (20, 0,  "️ Cena. Tirar basura después de las 20:00."),
        (20,30,  " Lectura y oración familiar."),
        (22, 0,  " Descanso. Revisá el pan para mañana."),
    ],
    "miercoles": [
        (6,  0,  "☀️ <b>Buenos días!</b> Hora del devocional."),
        (6, 45,  " Aprendizaje libre."),
        (8,  0,  " Desayuno."),
        (9,  0,  "️ Platos y mesa."),
        (9, 15,  " <b>Limpieza del día:</b> 2do piso — ordenar, hacer la cama, limpiar piso (20 min)."),
        (10, 0,  " Parque familiar!"),
        (12,30,  " Almuerzo: Pastas con salsa."),
        (14, 0,  " <b>Bloque de trabajo.</b>"),
        (16, 0,  "☕ Pausa."),
        (16,15,  " Workana o proyecto."),
        (18, 0,  " Tiempo con el bebé."),
        (20, 0,  "️ Cena. Basura después de las 20:00."),
        (20,30,  " Lectura y oración."),
        (22, 0,  " Descanso. Revisá el pan."),
    ],
    "jueves": [
        (6,  0,  "☀️ <b>Buenos días!</b> Devocional."),
        (6, 45,  " Aprendizaje libre."),
        (8,  0,  " Desayuno."),
        (9,  0,  "️ Platos y mesa."),
        (9, 15,  " <b>Limpieza del día:</b> Ordenar objetos generales (15 min)."),
        (10, 0,  " Parque!"),
        (12,30,  " Almuerzo: Pata y muslo al horno con papas."),
        (14, 0,  " <b>Bloque de trabajo.</b>"),
        (16, 0,  "☕ Pausa."),
        (16,15,  " Workana o proyecto."),
        (18, 0,  " Tiempo con el bebé."),
        (20, 0,  "️ Cena. No olvidés: <b>tirar basura Y reciclaje</b> después de las 20:00."),
        (20,30,  " Lectura y oración."),
        (22, 0,  " Descanso. Revisá el pan."),
    ],
    "viernes": [
        (6,  0,  "☀️ <b>Buenos días!</b> Devocional."),
        (6, 45,  " Aprendizaje libre."),
        (8,  0,  " Desayuno."),
        (9,  0,  "️ Platos y mesa."),
        (9, 15,  " <b>Limpieza del día:</b> Barrer y trapear (repaso, 20 min)."),
        (10, 0,  " Parque!"),
        (12,30,  " Almuerzo: Milanesas de pollo con puré."),
        (14, 0,  " <b>Bloque de trabajo.</b> Hoy terminás a las 17:00."),
        (17, 0,  "⛪ Hora de salir al grupo de iglesia. Buen encuentro!"),
        (22, 0,  " Llegaron a casa. Descansá bien."),
    ],
    "sabado": [
        (6,  0,  "☀️ <b>Buenos días!</b> Devocional."),
        (6, 45,  " Aprendizaje libre."),
        (8,  0,  " Desayuno."),
        (9,  0,  "️ Platos y mesa."),
        (9, 15,  " <b>Limpieza del día:</b> 2do piso + sacar reciclaje después de las 20:00."),
        (10, 0,  " Parque!"),
        (12,30,  " Almuerzo libre."),
        (14, 0,  " <b>Bloque de trabajo.</b> Terminás a las 17:00."),
        (17, 0,  "⛪ Salida a la iglesia. Que sea una linda reunión!"),
        (20, 0,  "️ No olvidés: <b>basura Y reciclaje</b> al llegar a casa."),
        (22, 0,  " Llegaron a casa. Descansá."),
    ],
    "domingo": [
        (6,  0,  "☀️ <b>Buenos días!</b> Devocional dominical."),
        (6, 45,  " Aprendizaje libre."),
        (8,  0,  " Desayuno familiar."),
        (9,  0,  "️ Platos y mesa."),
        (9, 15,  " <b>Limpieza del día</b> antes de salir."),
        (9, 50,  "⛪ Preparate para salir. Enlistarse a las 10:00."),
        (11, 0,  " Iglesia. Buen culto!"),
        (13,30,  " De vuelta a casa. Almuerzo."),
        (20, 0,  "️ Tirar basura. Revisar pan para mañana."),
        (22, 0,  " Buenas noches. Nueva semana mañana!"),
    ],
}

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

# ─── RESUMEN DEL DÍA ─────────────────────────────────────────────
RESUMEN = {
    "lunes":     " <b>Hoy es LUNES</b>\n Limpieza: Baño completo\n Almuerzo: Arroz con pollo | Cena: Tarta de pollo\n Trabajo: 14:00 - 18:00",
    "martes":    " <b>Hoy es MARTES</b>\n Limpieza: Barrer y trapear planta baja\n Almuerzo: Tarta de pollo | Cena: Milanesas de pollo\n Trabajo: 14:00 - 18:00",
    "miercoles": " <b>Hoy es MIÉRCOLES</b>\n Limpieza: 2do piso\n Almuerzo: Pastas | Cena: Arroz con huevo\n Trabajo: 14:00 - 18:00",
    "jueves":    " <b>Hoy es JUEVES</b>\n Limpieza: Ordenar objetos + reciclaje\n Almuerzo: Pata y muslo | Cena: Croquetas de atún\n Trabajo: 14:00 - 18:00",
    "viernes":   " <b>Hoy es VIERNES</b>\n Limpieza: Barrer y trapear (repaso)\n Almuerzo: Milanesas con puré | Cena: Pastas\n Trabajo: 14:00 - 17:00\n⛪ Grupo iglesia: 17:00",
    "sabado":    " <b>Hoy es SÁBADO</b>\n Limpieza: 2do piso + reciclaje\n Almuerzo: Libre | Cena: Libre\n Trabajo: 14:00 - 17:00\n⛪ Iglesia: 17:00",
    "domingo":   " <b>Hoy es DOMINGO</b>\n Limpieza: Antes de salir (9:15)\n Almuerzo libre\n⛪ Iglesia: 10:00 - 12:30",
}

# ─── HANDLERS ────────────────────────────────────────────────────
async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime
    dia = datetime.now(tz).strftime("%A").lower()
    dia_es = DIAS_SEMANA[["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].index(dia)]
    await update.message.reply_text(RESUMEN.get(dia_es, "No hay resumen para hoy."), parse_mode="HTML")

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
        "No inventes horarios ni actividades que no estén en mi agenda."
    )

async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    await update.message.chat.send_action("typing")
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": texto}
            ],
            max_tokens=500,
        )
        respuesta = response.choices[0].message.content
    except Exception as e:
        respuesta = f"Error al consultar la IA: {e}"
    await update.message.reply_text(respuesta)

# ─── ENVÍO PROGRAMADO ────────────────────────────────────────────
async def enviar_mensaje(bot, texto):
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
    app.add_handler(CommandHandler("hoy", hoy))
    app.add_handler(CommandHandler("ayuda", ayuda))
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

