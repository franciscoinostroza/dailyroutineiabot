import logging
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.calendar import leer_eventos
from bot.tools.trabajo import _calcular_horas
from bot.tools.resumen import pagos_proximos
from bot.tools.presupuestos import ver_presupuesto
from bot.services.sheets import WorksheetRecordatorios

tz = pytz.timezone(settings.timezone)

DIA_EN_ES = {
    "monday": "lunes", "tuesday": "martes", "wednesday": "miercoles",
    "thursday": "jueves", "friday": "viernes", "saturday": "sabado", "sunday": "domingo",
}


async def generar_briefing() -> str:
    ahora = datetime.now(tz)
    dia_es = DIA_EN_ES[ahora.strftime("%A").lower()]
    fecha = ahora.strftime("%d/%m/%Y")

    msg = f"☀️ Buenos dias Francisco — {dia_es} {fecha}\n\n"

    # Eventos de hoy
    try:
        eventos = leer_eventos(ahora.strftime("%Y-%m-%d"))
        if eventos:
            msg += "📅 Hoy tenes:\n"
            for e in eventos[:5]:
                hora = e["start"].get("dateTime", "")
                hora = hora[11:16] if "T" in hora else ""
                hora_str = f"{hora} " if hora else ""
                msg += f"  • {hora_str}{e.get('summary', 'Sin titulo')}\n"
            msg += "\n"
    except Exception as e:
        logging.error(f"Briefing: error leyendo eventos: {e}")

    # Horas trabajadas ayer
    try:
        ayer = (ahora - timedelta(days=1)).strftime("%Y-%m-%d")
        _, sesiones, por_proy = _calcular_horas()
        horas_ayer = sum(s["minutos"] / 60 for s in sesiones if s.get("fecha", "") == ayer)
        if horas_ayer > 0:
            msg += f"⏱ Ayer trabajaste: {horas_ayer:.1f}h\n"
            proyectos_ayer = {}
            for s in sesiones:
                if s.get("fecha", "") == ayer:
                    p = s.get("proyecto", "Sin proyecto")
                    proyectos_ayer[p] = proyectos_ayer.get(p, 0) + s["minutos"] / 60
            for p, h in proyectos_ayer.items():
                msg += f"  {p}: {h:.1f}h\n"
            msg += "\n"
    except Exception as e:
        logging.error(f"Briefing: error calculando horas: {e}")

    # Pagos proximos
    try:
        prox = pagos_proximos(dias_ventana=settings.payments_reminder_window_days)
        if prox:
            msg += "💳 Pagos:\n"
            for p in prox[:5]:
                d = p["dias_faltan"]
                icono = "🔴" if d == 0 else "🟡" if d <= 2 else "🟢"
                lbl = "HOY" if d == 0 else "manana" if d == 1 else f"en {d} dias"
                msg += f"  {icono} {p['nombre']} — ${float(p.get('monto',0)):,.0f} — {lbl}\n"
            msg += "\n"
    except Exception as e:
        logging.error(f"Briefing: error leyendo pagos: {e}")

    # Presupuestos
    try:
        pres = await ver_presupuesto()
        if pres and "No hay presupuestos" not in pres:
            msg += f"{pres}\n\n"
    except Exception as e:
        logging.error(f"Briefing: error leyendo presupuestos: {e}")

    # Recordatorios pendientes
    try:
        pendientes = WorksheetRecordatorios.read_pending()
        if pendientes:
            msg += f"📋 {len(pendientes)} recordatorios pendientes\n"
    except Exception:
        pass

    msg += "\n¡A meterle! 💪"
    return msg


async def enviar_briefing(bot) -> None:
    try:
        msg = await generar_briefing()
        await bot.send_message(chat_id=settings.chat_id, text=msg)
    except Exception as e:
        logging.error(f"Error en briefing matutino: {e}", exc_info=True)
