import json
import logging
from datetime import datetime
import pytz

from openai import AsyncOpenAI

from bot.config import settings
from bot.tools.registry import TOOLS, execute_tool

tz = pytz.timezone(settings.timezone)
openai_client = AsyncOpenAI(api_key=settings.openai_key)

DIAS_VALIDOS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIA_EN_ES = {
    "monday": "lunes", "tuesday": "martes", "wednesday": "miercoles",
    "thursday": "jueves", "friday": "viernes", "saturday": "sabado", "sunday": "domingo",
}

TELEGRAM_BUTTON_MAP = {
    "📅 Rutina": "ver_rutina_diaria",
    "💳 Pagos": "ver_pagos",
    "🛒 Gastos": "ver_gastos",
    "⏱ Trabajo": "ver_horas_trabajadas",
    "📋 Tareas": "ver_recordatorios_pendientes",
    "📊 Resumen": "resumen_semanal_tool",
}


def dia_hoy_es() -> str:
    return DIA_EN_ES[datetime.now(tz).strftime("%A").lower()]


def _build_system_prompt() -> str:
    ahora = datetime.now(tz)
    dia_es = dia_hoy_es()
    hora_actual = ahora.strftime("%H:%M")
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    return (
        "Sos el asistente personal de Francisco. Lo ayudas con su rutina diaria y sus compras.\n"
        "LLamalo siempre Francisco, nunca 'amigo' ni 'usuario'.\n\n"
        f"HOY ES {dia_es.upper()} {fecha_hoy}, SON LAS {hora_actual} (hora de Argentina).\n\n"
        "SUPERMERCADOS: Coto, Carrefour, Dia.\n"
        "BILLETERAS: MercadoPago, Brubank, Uala, PersonalPay, Supervielle, Banco Ciudad, Banco del Sol, Prex.\n\n"
        "Francisco es freelancer en Workana (desarrollo web). Vive con su esposa y su bebe.\n"
        "Tenes 2 sistemas de agenda, NO los confundas:\n"
        "  🗓 CALENDARIO (Google Calendar) → eventos PUNTUALES con fecha: reuniones, citas, turnos, medico, videollamada.\n"
        "    Tools: crear_evento_calendario, ver_eventos_calendario, eliminar_evento_calendario.\n"
        "  📋 RUTINA (Google Sheets) → actividades RECURRENTES cada semana: medicacion, ejercicio, lectura.\n"
        "    Tools: agregar_a_rutina, quitar_de_rutina, ver_rutina_diaria.\n"
        "    Palabras clave: 'rutina', 'todos los dias', 'cada lunes', 'medicacion', 'ejercicio', 'leer'.\n"
        "USA LAS HERRAMIENTAS. Cuando Francisco te pida hacer algo concreto, llama la herramienta.\n"
        "No finjas que hiciste algo sin haber llamado la herramienta. Confirma el resultado.\n"
        "Si dice 'reunion', 'cita', 'turno', 'medico', 'videollamada', 'evento' → usa crear_evento_calendario.\n"
        "Si dice 'agrega a mi rutina', 'todos los lunes', 'cada martes', 'medicacion' → usa agregar_a_rutina.\n"
        "Si dice 'empiezo a trabajar en X' → usa iniciar_trabajo_tool.\n"
        "Si dice 'termine', 'corte' → usa terminar_trabajo_tool.\n"
        "Si dice 'compre X a $Y en Z con W' → usa registrar_compra.\n"
        "Si dice 'agrega el pago de X' o 'X vence el dia Y' → usa agregar_pago.\n"
        "Si dice 'recordame X' → usa agregar_recordatorio_puntual.\n"
        "NUNCA respondas 'listo' o 'agendado' sin haber llamado la herramienta.\n"
        "Si Francisco pregunta 'como viene mi dia', 'que tengo que hacer', consulta ver_rutina_diaria primero.\n"
        "Botones rapidos que puede usar:\n"
        "  '📅 Rutina' → ver_rutina_diaria\n"
        "  '💳 Pagos' → ver_pagos\n"
        "  '🛒 Gastos' → ver_gastos\n"
        "  '⏱ Trabajo' → ver_horas_trabajadas\n"
        "  '📋 Tareas' → ver_recordatorios_pendientes\n"
        "  '📊 Resumen' → resumen_semanal_tool\n"
        "Tambien podes usar:\n"
        "  agregar_presupuesto — definir presupuesto mensual por categoria\n"
        "  ver_presupuesto — ver estado de presupuestos con barras de progreso\n"
        "  crear_proyecto — crear un nuevo proyecto freelance\n"
        "  ver_proyecto_info — consultar horas, docs y estado de un proyecto\n"
        "  registrar_habito — completar un habito diario (ejercicio, lectura, etc.)\n"
        "  ver_habitos — ver rachas y adherencia del mes\n"
        "  agregar_deadline — fecha de entrega de un proyecto\n"
        "  ver_deadlines — deadlines activos con dias habiles\n"
        "  agregar_factura — registrar una factura freelance\n"
        "  ver_facturas — facturas del mes con totales USD/ARS\n"
        "Francisco puede mandarte notas de voz (las transcribo automaticamente) y fotos de tickets de compra (los proceso con OCR).\n"
        "Responde siempre en espanol, de forma calida, natural y cercana, sin markdown ni asteriscos.\n"
        "No uses frases roboticas como 'en lenguaje natural' o 'asistente virtual'."
    )


class AIAssistant:
    def __init__(self):
        self._histories: dict[str, list[dict]] = {}

    def get_history(self, chat_id: str) -> list[dict]:
        if chat_id not in self._histories:
            self._histories[chat_id] = []
        h = self._histories[chat_id]
        if len(h) > settings.max_conversation_history:
            del h[:-settings.max_conversation_history]
        return h

    def append_user(self, chat_id: str, text: str):
        self.get_history(chat_id).append({"role": "user", "content": text})

    def append_assistant(self, chat_id: str, text: str):
        self.get_history(chat_id).append({"role": "assistant", "content": text})

    async def process_message(self, text: str, chat_id: str) -> str:
        self.append_user(chat_id, text)
        h = self.get_history(chat_id)

        messages = [{"role": "system", "content": _build_system_prompt()}] + h.copy()

        for _ in range(settings.openai_max_tool_rounds):
            try:
                response = await openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    max_tokens=settings.openai_max_tokens,
                )
            except Exception as e:
                logging.error(f"OpenAI API error: {e}")
                raise

            msg = response.choices[0].message
            logging.info(
                f"IA response: tool_calls={bool(msg.tool_calls)}, "
                f"content={msg.content[:80] if msg.content else 'None'}"
            )

            if not msg.tool_calls:
                respuesta = msg.content or "Listo."
                self.append_assistant(chat_id, respuesta)
                return respuesta

            messages.append(msg)
            for tc in msg.tool_calls:
                nombre = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                logging.info(f"IA llamo herramienta: {nombre}({json.dumps(args, ensure_ascii=False)})")
                try:
                    resultado = await execute_tool(nombre, args)
                except Exception as e:
                    resultado = f"Error al ejecutar {nombre}: {e}"
                    logging.error(f"Error en herramienta {nombre}: {e}", exc_info=True)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": resultado,
                })

        return "Hmm, hice varias cosas. Necesitas algo mas?"


ai_assistant = AIAssistant()
