from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from telegram.ext import ContextTypes
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.calendar import leer_eventos
from bot.tools.rutina import MENSAJES_DIA, RESUMEN, DIAS_VALIDOS, cargar_agenda
from bot.services.auth import reset_auth_cache

tz = pytz.timezone(settings.timezone)

TECLADO = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 Rutina"), KeyboardButton("💳 Pagos"), KeyboardButton("🛒 Gastos")],
        [KeyboardButton("⏱ Trabajo"), KeyboardButton("📋 Tareas"), KeyboardButton("📊 Resumen")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Escribime o toca un boton..."
)

DIA_EN_ES = {
    "monday": "lunes", "tuesday": "martes", "wednesday": "miercoles",
    "thursday": "jueves", "friday": "viernes", "saturday": "sabado", "sunday": "domingo",
}


def dia_hoy_es() -> str:
    return DIA_EN_ES[datetime.now(tz).strftime("%A").lower()]


async def start(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    nombre = update.effective_user.first_name or "ahi"
    username = update.effective_user.username or "sin username"

    if chat_id == str(settings.chat_id):
        await update.message.reply_text(
            f"👋 ¡Hola {nombre}! Aca estoy para lo que necesites.\n\n"
            "Toca los botones de abajo o escribime lo que quieras.\n"
            "Para ver todo lo que puedo hacer: /ayuda",
            reply_markup=TECLADO,
        )

    elif settings.chat_id_esposa and chat_id == str(settings.chat_id_esposa):
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Ver eventos de hoy", callback_data="agenda_hoy")],
            [InlineKeyboardButton("📅 Ver eventos de manana", callback_data="agenda_manana")],
            [InlineKeyboardButton("💳 Descuentos de hoy", callback_data="descuentos_hoy")],
        ])
        await update.message.reply_text(
            f"👋 Hola {nombre}!\n\nQue queres hacer?",
            reply_markup=botones,
        )

    else:
        await update.message.reply_text(
            f"👋 Hola {nombre}!\n\n"
            f"Este es un bot privado. Tu solicitud fue enviada al administrador."
        )
        await context.bot.send_message(
            chat_id=settings.chat_id,
            text=f"⚠️ Nueva persona intento usar el bot:\n\n"
                 f"Nombre: {nombre}\n"
                 f"Username: @{username}\n"
                 f"Chat ID: `{chat_id}`",
            parse_mode="Markdown",
        )


async def ayuda(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Soy tu asistente personal.\n\n"
        "Toca los botones fijos de abajo o hablame como quieras:\n\n"
        "• 📋 Rutina diaria (medicacion, ejercicio, leer)\n"
        "• 🗓 Calendario (reuniones, citas, turnos, medico)\n"
        "• 💳 Pagos y suscripciones\n"
        "• 🛒 Compras con descuentos\n"
        "• ⏱ Horas de trabajo freelance\n"
        "• 📅 Eventos en Google Calendar\n"
        "• 📋 Recordatorios puntuales\n\n"
        "Comandos: /hoy /listar /compra /evento /gastos /pagos /recargar /test "
        "/agenda /agregar /borrar /donde /descuentos /historial /pago /eliminar_evento"
    )


async def test(update, context: ContextTypes.DEFAULT_TYPE):
    estado = f"{sum(len(v) for v in MENSAJES_DIA.values())} recordatorios cargados" \
             if MENSAJES_DIA else "⚠️ agenda vacia — usa /recargar"
    await update.message.reply_text(f"✅ Bot funcionando.\n📋 Agenda: {estado}")
