import logging
import random
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.tools.trabajo import _calcular_horas

tz = pytz.timezone(settings.timezone)

_MEDIODIA_FRASES = [
    "🌤 Mediodia. ¿Ya almorzaste? Van {horas}h trabajadas hoy. ¡Estirate un toque!",
    "🥗 Hora del almuerzo. Hoy llevas {horas}h. Dale un respiro a los ojos.",
    "☀️ Mitad del dia. {horas}h metidas. ¿Te preparas un cafecito?",
    "🍝 Pausa. Van {horas}h de trabajo. Date 20 minutos aunque sea.",
    "⏰ Mediodia clavado. {horas}h acumuladas. Salí a caminar 5 min si podés.",
]

_CIERRE_FRASES = [
    "🌙 Che Francisco, ya son las 21. ¿Cómo terminaste el dia?",
    "🌛 Se hizo tarde. ¿Repasamos el dia o te desconectaste hace rato?",
    "😴 Último ping del dia. ¿Contento con lo que hiciste hoy?",
    "🌜 Cierre de jornada. Mañana briefing a las 8. ¿Algo que quieras anotar?",
]

_FINDE_FRASES = [
    "🎉 ¡Viernes! Buena semana. Disfrutá el finde.",
    "🥳 ¡Al fin viernes! Merecido descanso. ¿Planazos?",
]

_LUNES_FRASES = [
    "💪 Arranca la semana nueva. ¿Con qué proyecto le metemos hoy?",
    "🚀 Lunes. Hoja en blanco. ¿Qué prioridad tenés esta semana?",
    "📋 Nueva semana. ¿Repasamos deadlines y objetivos?",
]


async def enviar_pulso_mediodia(bot) -> None:
    try:
        horas, _, _ = _calcular_horas()
        hoy = datetime.now(tz).strftime("%Y-%m-%d")
        _, sesiones, _ = _calcular_horas()
        horas_hoy = sum(s["minutos"] / 60 for s in sesiones if s.get("fecha", "") == hoy)
        frase = random.choice(_MEDIODIA_FRASES).format(horas=f"{horas_hoy:.1f}")

        await bot.send_message(chat_id=settings.chat_id, text=frase)
    except Exception as e:
        logging.error(f"Error en pulso mediodia: {e}")


async def enviar_pulso_cierre(bot) -> None:
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        frase = random.choice(_CIERRE_FRASES)
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("😊 Bien", callback_data="mood_bien"),
             InlineKeyboardButton("😐 Maso", callback_data="mood_maso"),
             InlineKeyboardButton("😞 Mal", callback_data="mood_mal")],
            [InlineKeyboardButton("📝 Dejar nota", callback_data="mood_nota")],
        ])
        await bot.send_message(chat_id=settings.chat_id, text=frase, reply_markup=botones)
    except Exception as e:
        logging.error(f"Error en pulso cierre: {e}")


async def enviar_saludo_dia(bot) -> None:
    try:
        hoy = datetime.now(tz)
        if hoy.weekday() == 4:
            frase = random.choice(_FINDE_FRASES)
            await bot.send_message(chat_id=settings.chat_id, text=frase)
        elif hoy.weekday() == 0:
            frase = random.choice(_LUNES_FRASES)
            await bot.send_message(chat_id=settings.chat_id, text=frase)
    except Exception as e:
        logging.error(f"Error en saludo del dia: {e}")
