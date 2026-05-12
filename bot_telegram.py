"""
BOT DE TELEGRAM - MI SISTEMA DE VIDA
=====================================
Variables de entorno requeridas:
  TOKEN, CHAT_ID, OPENAI_KEY, SHEET_ID, TIMEZONE
  GOOGLE_CREDENTIALS  ← JSON completo del service account (Railway)
  CREDENTIALS_FILE    ← alternativa local (default: credentials.json)
"""

import json
import logging
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from openai import AsyncOpenAI
import gspread
from googleapiclient.discovery import build
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
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")   # JSON string para Railway
openai_client    = AsyncOpenAI(api_key=os.getenv("OPENAI_KEY"))
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
tz = pytz.timezone(TIMEZONE)

DIAS_VALIDOS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_SEMANA  = DIAS_VALIDOS
DIA_EN_ES    = {
    "monday":"lunes","tuesday":"martes","wednesday":"miercoles",
    "thursday":"jueves","friday":"viernes","saturday":"sabado","sunday":"domingo"
}

MENSAJES_DIA: dict = {}
RESUMEN:      dict = {}

TECLADO = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 Hoy"), KeyboardButton("💳 Pagos"), KeyboardButton("🛒 Gastos")],
        [KeyboardButton("⏱ Trabajo"), KeyboardButton("📋 Tareas"), KeyboardButton("📊 Resumen")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Escribime o tocá un botón..."
)

# ─── HERRAMIENTAS PARA LA IA ─────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "agregar_recordatorio",
            "description": "Agrega un recordatorio a la agenda diaria de Francisco",
            "parameters": {
                "type": "object",
                "properties": {
                    "dia": {"type": "string", "enum": ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]},
                    "hora": {"type": "integer", "minimum": 0, "maximum": 23},
                    "minuto": {"type": "integer", "minimum": 0, "maximum": 59},
                    "mensaje": {"type": "string"}
                },
                "required": ["dia", "hora", "minuto", "mensaje"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "borrar_recordatorio",
            "description": "Elimina un recordatorio de la agenda",
            "parameters": {
                "type": "object",
                "properties": {
                    "dia": {"type": "string", "enum": ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]},
                    "hora": {"type": "integer", "minimum": 0, "maximum": 23},
                    "minuto": {"type": "integer", "minimum": 0, "maximum": 59}
                },
                "required": ["dia", "hora", "minuto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_compra",
            "description": "Registra una compra con supermercado y billetera. El bot calcula automáticamente los descuentos disponibles hoy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto": {"type": "string"},
                    "cantidad": {"type": "number"},
                    "precio_unitario": {"type": "number"},
                    "supermercado": {"type": "string", "enum": ["Coto", "Carrefour", "Día"]},
                    "billetera": {"type": "string", "enum": ["MercadoPago", "Brubank", "Ualá", "PersonalPay", "Supervielle", "Banco Ciudad", "Banco del Sol", "Prex"]}
                },
                "required": ["producto", "cantidad", "precio_unitario", "supermercado", "billetera"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_pago",
            "description": "Agrega un pago recurrente o suscripción al sistema de recordatorios",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "dia_vencimiento": {"type": "integer", "minimum": 1, "maximum": 31},
                    "monto": {"type": "number"},
                    "categoria": {"type": "string", "description": "Opcional"}
                },
                "required": ["nombre", "dia_vencimiento", "monto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_pago_pagado",
            "description": "Marca un pago como pagado en el mes actual para que no siga apareciendo en recordatorios",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"}
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_pagos",
            "description": "Muestra todos los pagos y suscripciones registrados y su estado",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_gastos",
            "description": "Muestra el resumen de gastos del mes actual con totales y ahorros",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_descuentos",
            "description": "Muestra los descuentos disponibles hoy en supermercados con billeteras",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_agenda",
            "description": "Muestra la agenda semanal completa de Francisco con todos los recordatorios",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_evento_calendario",
            "description": "Crea un evento en Google Calendar. USALA cada vez que Francisco pida agendar, crear, anotar o programar un evento, reunión, cita o turno. Calculá la fecha real a partir de la fecha indicada en el mensaje del sistema (hoy). NO uses fechas inventadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD. Calculala a partir del mensaje del sistema que dice la fecha de hoy."},
                    "hora_inicio": {"type": "string", "description": "Hora de inicio HH:MM (formato 24h)"},
                    "hora_fin": {"type": "string", "description": "Hora de fin HH:MM (formato 24h)"},
                    "titulo": {"type": "string", "description": "Título del evento"}
                },
                "required": ["fecha", "hora_inicio", "hora_fin", "titulo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_eventos_calendario",
            "description": "Lista los eventos del calendario de Francisco para un día específico",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha YYYY-MM-DD. 'hoy' o 'mañana' también son válidos."}
                },
                "required": ["fecha"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_evento_calendario",
            "description": "Elimina un evento del calendario por su número (1, 2, 3...) según la última lista de eventos consultada",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer", "minimum": 1, "description": "Número del evento a eliminar (1 = primero)"}
                },
                "required": ["indice"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "iniciar_trabajo_tool",
            "description": "Inicia una sesión de trabajo freelance. Usala cuando Francisco diga que empieza a trabajar en un proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proyecto": {"type": "string", "description": "Nombre del proyecto (ej: 'Web Cliente X')"},
                    "descripcion": {"type": "string", "description": "Opcional. Detalle de la tarea."}
                },
                "required": ["proyecto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminar_trabajo_tool",
            "description": "Termina la sesión de trabajo activa. Usala cuando Francisco diga que terminó de trabajar, 'corté', 'terminé', etc.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_horas_trabajadas",
            "description": "Muestra las horas trabajadas en el mes actual, por proyecto",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_recordatorio_puntual",
            "description": "Agrega un recordatorio puntual (tarea, pendiente, cosa para hacer). NO es para agenda diaria, es para cosas sueltas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string", "description": "El texto del recordatorio"}
                },
                "required": ["texto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_recordatorios_pendientes",
            "description": "Muestra los recordatorios puntuales pendientes",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_recordatorio_hecho",
            "description": "Marca un recordatorio puntual como hecho por su número (1, 2, 3...)",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer", "minimum": 1, "description": "Número del recordatorio (1 = primero)"}
                },
                "required": ["indice"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_semanal_tool",
            "description": "Genera un resumen semanal con gastos, horas trabajadas, pagos próximos y eventos",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

# ─── CONEXIÓN SHEETS (con cache) ─────────────────────────────────
_gc_cache = None

def get_gc():
    global _gc_cache
    if _gc_cache is not None:
        return _gc_cache
    scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar"
]
    if GOOGLE_CREDS_JSON:
        raw = GOOGLE_CREDS_JSON.strip()
        # Intenta JSON directo; si falla, asume base64
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            import base64
            info = json.loads(base64.b64decode(raw).decode("utf-8"))
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        logging.info("Google auth: usando GOOGLE_CREDENTIALS (env var)")
    else:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        logging.info(f"Google auth: usando archivo {CREDENTIALS_FILE}")
    _gc_cache = gspread.authorize(creds)
    return _gc_cache

def get_worksheet(name="Agenda"):
    return get_gc().open_by_key(SHEET_ID).worksheet(name)

def get_calendar():
    cal_id = os.getenv("CALENDAR_ID", "primary")
    logging.info(f"Inicializando Google Calendar API para calendario: {cal_id}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar"
    ]
    if GOOGLE_CREDS_JSON:
        raw = GOOGLE_CREDS_JSON.strip()
        try:
            info = json.loads(raw)
        except json.JSONDecodeError:
            import base64
            info = json.loads(base64.b64decode(raw).decode("utf-8"))
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return build("calendar", "v3", credentials=creds)

def crear_evento(titulo, inicio, fin, descripcion=""):
    service = get_calendar()
    cal_id = os.getenv("CALENDAR_ID", "primary")
    evento = {
        "summary": titulo,
        "description": descripcion,
        "start": {"dateTime": inicio, "timeZone": TIMEZONE},
        "end": {"dateTime": fin, "timeZone": TIMEZONE},
    }
    logging.info(f"Creando evento en calendario {cal_id}: {titulo} {inicio}-{fin}")
    resultado = service.events().insert(calendarId=cal_id, body=evento).execute()
    logging.info(f"Evento creado OK: {resultado.get('id')}")
    return resultado

def leer_eventos(dia_str):
    from datetime import datetime, timedelta
    import pytz
    tz_local = pytz.timezone(TIMEZONE)
    fecha = datetime.strptime(dia_str, "%Y-%m-%d")
    inicio = tz_local.localize(fecha.replace(hour=0, minute=0, second=0))
    fin = tz_local.localize(fecha.replace(hour=23, minute=59, second=59))
    service = get_calendar()
    resultado = service.events().list(
        calendarId=os.getenv("CALENDAR_ID", "primary"),
        timeMin=inicio.isoformat(),
        timeMax=fin.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return resultado.get("items", [])

def eliminar_evento(evento_id):
    service = get_calendar()
    service.events().delete(
        calendarId=os.getenv("CALENDAR_ID", "primary"),
        eventId=evento_id
    ).execute()

def dia_hoy_es():
    return DIA_EN_ES[datetime.now(tz).strftime("%A").lower()]

def es_ultimo_sabado():
    hoy = datetime.now(tz)
    if hoy.weekday() != 5:
        return False
    from calendar import monthrange
    return hoy.day + 7 > monthrange(hoy.year, hoy.month)[1]

def parsear_tope(raw):
    if not raw or str(raw).strip().lower() in ("", "sin tope", "-"):
        return None
    nums = re.sub(r"[^\d]", "", str(raw))
    return float(nums) if nums else None

def descuentos_del_dia(dia_es: str) -> list:
    try:
        rows = get_worksheet("Descuentos").get_all_records()
    except Exception as e:
        logging.error(f"Error leyendo Descuentos: {e}")
        return []
    resultado = []
    for r in rows:
        d = str(r.get("dia", "")).lower()
        if d == dia_es:
            resultado.append(r)
        elif d == "sabado_ultimo" and dia_es == "sabado" and es_ultimo_sabado():
            resultado.append(r)
    return resultado


# ─── PAGOS / SUSCRIPCIONES ───────────────────────────────────────
def get_worksheet_pagos():
    gc = get_gc()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet("Pagos")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Pagos", rows=100, cols=10)
        ws.append_row(["nombre", "monto", "dia_vencimiento", "categoria", "activo", "ultimo_mes"])
        logging.info("Hoja 'Pagos' creada automáticamente.")
        return ws

def leer_pagos(solo_activos=True):
    try:
        rows = get_worksheet_pagos().get_all_records()
    except Exception as e:
        logging.error(f"Error leyendo Pagos: {e}")
        return []
    if solo_activos:
        rows = [r for r in rows if str(r.get("activo", "si")).lower() != "no"]
    return rows

def _proxima_fecha_vencimiento(dia_venc):
    hoy = datetime.now(tz)
    from calendar import monthrange
    for offset in (0, 1):
        mes = hoy.month + offset
        ano = hoy.year
        if mes > 12:
            mes, ano = 1, ano + 1
        max_dia = monthrange(ano, mes)[1]
        dia = min(dia_venc, max_dia)
        fecha = hoy.replace(year=ano, month=mes, day=dia)
        if fecha.date() >= hoy.date():
            return fecha
    return None

def pagos_proximos(dias_ventana=3):
    hoy = datetime.now(tz)
    mes_actual = hoy.strftime("%Y-%m")
    pagos = leer_pagos(solo_activos=True)
    resultado = []
    for p in pagos:
        if str(p.get("ultimo_mes", "")) == mes_actual:
            continue
        dia_venc = int(p.get("dia_vencimiento", 0))
        if dia_venc <= 0:
            continue
        fecha_venc = _proxima_fecha_vencimiento(dia_venc)
        if fecha_venc is None:
            continue
        dias_faltan = (fecha_venc.date() - hoy.date()).days
        if 0 <= dias_faltan <= dias_ventana:
            resultado.append({**p, "dias_faltan": dias_faltan})
    return sorted(resultado, key=lambda x: x["dias_faltan"])

async def notificar_pagos(bot):
    try:
        proximos = pagos_proximos()
        if not proximos:
            return
        msg = "📅 Recordatorio de pagos:\n\n"
        for p in proximos:
            dias = p["dias_faltan"]
            icono = "🔴" if dias == 0 else "🟡" if dias <= 2 else "🟢"
            label = "HOY" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
            msg += f"{icono} {p['nombre']} — ${float(p.get('monto',0)):,.0f} — {label}\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg)
        esposa = os.getenv("CHAT_ID_ESPOSA", "")
        if esposa:
            await bot.send_message(chat_id=esposa, text=msg)
    except Exception as e:
        logging.error(f"Error en notificar_pagos: {e}")


# ─── TRABAJO / FREELANCE ────────────────────────────────────────
def get_worksheet_trabajo():
    gc = get_gc()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet("Trabajo")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Trabajo", rows=200, cols=10)
        ws.append_row(["fecha", "proyecto", "hora_inicio", "hora_fin", "descripcion", "estado"])
        logging.info("Hoja 'Trabajo' creada automáticamente.")
        return ws

def sesion_activa():
    try:
        rows = get_worksheet_trabajo().get_all_records()
    except Exception:
        return None
    for r in reversed(rows):
        if str(r.get("estado", "")).lower() == "activo":
            return r
    return None

def _iniciar_trabajo(proyecto, descripcion=""):
    activa = sesion_activa()
    resultado = ""
    if activa:
        _cerrar_sesion_trabajo()
        resultado = f"(Se cerró sesión anterior: {activa.get('proyecto','')}). "
    ahora = datetime.now(tz)
    get_worksheet_trabajo().append_row([
        ahora.strftime("%Y-%m-%d"), proyecto, ahora.strftime("%H:%M"), "", descripcion, "activo"
    ])
    return resultado + f"Sesión iniciada: {proyecto} a las {ahora.strftime('%H:%M')}"

def _cerrar_sesion_trabajo():
    activa = sesion_activa()
    if not activa:
        return "No hay sesión activa."
    ws = get_worksheet_trabajo()
    rows = ws.get_all_values()
    fila = len(rows)
    ahora = datetime.now(tz).strftime("%H:%M")
    ws.update(f"D{fila}", ahora)
    ws.update(f"F{fila}", "terminado")
    proyecto = rows[fila - 1][1] if fila > 1 else ""
    return f"Sesión terminada: {proyecto} a las {ahora}"

def _calcular_horas(mes=None):
    if mes is None:
        mes = datetime.now(tz).strftime("%Y-%m")
    try:
        rows = get_worksheet_trabajo().get_all_records()
    except Exception:
        return 0, [], {}
    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes) and str(r.get("estado", "")).lower() == "terminado"]
    total_min = 0
    por_proyecto = {}
    sesiones = []
    for r in filas:
        try:
            h_i = datetime.strptime(r["hora_inicio"], "%H:%M")
            h_f = datetime.strptime(r["hora_fin"], "%H:%M")
            mins = (h_f - h_i).seconds / 60
            total_min += mins
            proy = r.get("proyecto", "Sin proyecto")
            por_proyecto[proy] = por_proyecto.get(proy, 0) + mins
            sesiones.append({**r, "minutos": mins})
        except Exception:
            pass
    return total_min / 60, sesiones, por_proyecto


# ─── RECORDATORIOS PUNTUALES ────────────────────────────────────
def get_worksheet_recordatorios():
    gc = get_gc()
    sh = gc.open_by_key(SHEET_ID)
    try:
        return sh.worksheet("Recordatorios")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Recordatorios", rows=100, cols=5)
        ws.append_row(["texto", "fecha_creacion", "estado"])
        logging.info("Hoja 'Recordatorios' creada automáticamente.")
        return ws

def _leer_recordatorios_pendientes():
    try:
        rows = get_worksheet_recordatorios().get_all_records()
    except Exception:
        return []
    return [r for r in rows if str(r.get("estado", "")).lower() != "hecho"]

async def notificar_recordatorios(bot):
    try:
        pendientes = _leer_recordatorios_pendientes()
        if not pendientes:
            return
        msg = "📋 Recordatorios pendientes:\n\n"
        for i, r in enumerate(pendientes, 1):
            msg += f"{i}. {r['texto']}\n"
        msg += "\nHablame para marcarlos como hechos."
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        logging.error(f"Error en notificar_recordatorios: {e}")


# ─── RESUMEN SEMANAL ───────────────────────────────────────────
async def enviar_resumen_semanal(bot):
    try:
        from datetime import timedelta
        hoy = datetime.now(tz).date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        fin_semana = inicio_semana + timedelta(days=6)

        try:
            rows_hist = get_worksheet("Historial").get_all_records()
            filas_semana = [r for r in rows_hist if inicio_semana.strftime("%Y-%m-%d") <= str(r.get("fecha", "")) <= fin_semana.strftime("%Y-%m-%d")]
        except Exception:
            filas_semana = []

        total_final = sum(float(r.get("precio_final", 0)) for r in filas_semana)
        total_ahorro = sum(float(r.get("ahorro", 0)) for r in filas_semana)

        horas, sesiones, por_proy = _calcular_horas(mes=hoy.strftime("%Y-%m"))
        horas_semana = 0
        for s in sesiones:
            try:
                if inicio_semana.strftime("%Y-%m-%d") <= s.get("fecha", "") <= fin_semana.strftime("%Y-%m-%d"):
                    horas_semana += s["minutos"] / 60
            except Exception:
                pass

        proximos = pagos_proximos(dias_ventana=5)

        eventos = []
        for i in range(7):
            dia = inicio_semana + timedelta(days=i)
            try:
                evs = leer_eventos(dia.strftime("%Y-%m-%d"))
                for e in evs:
                    eventos.append({"fecha": dia.strftime("%d/%m"), "titulo": e.get("summary", "")})
            except Exception:
                pass

        pendientes = _leer_recordatorios_pendientes()

        msg = f"📊 RESUMEN SEMANAL\n{inicio_semana.strftime('%d/%m')} al {fin_semana.strftime('%d/%m')}\n\n"

        if filas_semana:
            msg += f"💵 Gastos: {len(filas_semana)} compras — ${total_final:,.0f} (ahorraste ${total_ahorro:,.0f})\n"
        else:
            msg += "💵 Sin gastos esta semana\n"

        if horas_semana > 0:
            msg += f"⏱ Trabajo: {horas_semana:.1f} horas\n"
            for proy, mins in por_proy.items():
                msg += f"  {proy}: {mins / 60:.1f}h\n"

        if eventos:
            msg += f"\n📅 Eventos de la semana ({len(eventos)}):\n"
            for e in eventos[:5]:
                msg += f"  {e['fecha']} — {e['titulo']}\n"

        if proximos:
            msg += "\n🔴 Pagos próximos:\n"
            for p in proximos[:3]:
                dias = p["dias_faltan"]
                label = "HOY" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
                msg += f"  {p['nombre']} — {label}\n"

        if pendientes:
            msg += f"\n📋 {len(pendientes)} recordatorios pendientes"

        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        logging.error(f"Error en resumen semanal: {e}", exc_info=True)


# ─── CARGA DE AGENDA ─────────────────────────────────────────────
def cargar_agenda():
    global MENSAJES_DIA, RESUMEN
    try:
        rows = get_worksheet("Agenda").get_all_records()
        mensajes = {}
        for row in rows:
            dia    = str(row["dia"]).strip().lower()
            hora   = int(row["hora"])
            minuto = int(row["minuto"])
            msg    = str(row["mensaje"])
            mensajes.setdefault(dia, []).append((hora, minuto, msg))
        resumen = {}
        for dia, lista in mensajes.items():
            for h, m, txt in lista:
                if h == 6 and m == 0:
                    resumen[dia] = txt
                    break
        MENSAJES_DIA = mensajes
        RESUMEN      = resumen
        total = sum(len(v) for v in mensajes.values())
        logging.info(f"Agenda cargada: {total} mensajes en {len(mensajes)} días.")
        return True, None
    except Exception as e:
        logging.error(f"Error cargando agenda: {e}")
        return False, str(e)


# ─── AGENDA COMMANDS ─────────────────────────────────────────────
# Variable global para guardar los últimos eventos consultados
_ultimos_eventos = []

async def agenda_calendar(update, context: ContextTypes.DEFAULT_TYPE):
    global _ultimos_eventos
    from datetime import datetime, timedelta
    
    hoy = datetime.now(tz).date()
    
    DIAS_MAP = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
    }

    if not context.args:
        fecha = hoy
    else:
        arg = context.args[0].lower()
        if arg == "hoy":
            fecha = hoy
        elif arg in ("mañana", "manana"):
            fecha = hoy + timedelta(days=1)
        elif arg in DIAS_MAP:
            dias_hasta = (DIAS_MAP[arg] - hoy.weekday()) % 7
            dias_hasta = dias_hasta if dias_hasta > 0 else 7
            fecha = hoy + timedelta(days=dias_hasta)
        elif "/" in arg:
            try:
                dia, mes = arg.split("/")
                fecha = hoy.replace(day=int(dia), month=int(mes))
            except:
                await update.message.reply_text("Formato inválido. Usá: /agenda hoy, mañana, lunes, o 06/05")
                return
        else:
            try:
                fecha = datetime.strptime(arg, "%Y-%m-%d").date()
            except:
                await update.message.reply_text("Formato inválido. Usá: /agenda hoy, mañana, lunes, o 06/05")
                return

    dia_str = fecha.strftime("%Y-%m-%d")
    dia_legible = fecha.strftime("%d/%m/%Y")

    try:
        eventos = leer_eventos(dia_str)
        _ultimos_eventos = eventos  # guardar para eliminar_evento
        if not eventos:
            await update.message.reply_text(f"Sin eventos en el calendario para el {dia_legible}.")
            return
        msg = f"📅 Eventos del {dia_legible}:\n\n"
        for i, e in enumerate(eventos, 1):
            hora = e["start"].get("dateTime", e["start"].get("date", ""))
            hora = hora[11:16] if "T" in hora else "Todo el día"
            msg += f"{i}. {hora} — {e.get('summary', 'Sin título')}\n"
        msg += "\nPara eliminar uno: /eliminar_evento <número>"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def eliminar_evento_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    global _ultimos_eventos
    if not _ultimos_eventos:
        await update.message.reply_text(
            "Primero consultá los eventos con /agenda hoy (o el día que quieras)."
        )
        return
    if not context.args:
        await update.message.reply_text("Indicá el número del evento a eliminar.\nEjemplo: /eliminar_evento 1")
        return
    try:
        indice = int(context.args[0]) - 1
        if indice < 0 or indice >= len(_ultimos_eventos):
            await update.message.reply_text(f"Número inválido. Hay {len(_ultimos_eventos)} eventos.")
            return
        titulo = _ultimos_eventos[indice].get("summary", "Sin título")
        eliminar_evento(_ultimos_eventos[indice]["id"])
        _ultimos_eventos.pop(indice)
        await update.message.reply_text(f"🗑 Evento eliminado: {titulo}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    dia_es = dia_hoy_es()
    texto  = RESUMEN.get(dia_es)
    if not texto:
        await update.message.reply_text(
            f"No hay resumen para hoy ({dia_es}).\n"
            "Si la agenda está vacía usá /recargar para sincronizar desde Google Sheets."
        )
        return
    await update.message.reply_text(texto)

async def listar(update, context: ContextTypes.DEFAULT_TYPE):
    if not MENSAJES_DIA:
        await update.message.reply_text(
            "La agenda está vacía. Probá con /recargar para sincronizar desde Google Sheets."
        )
        return
    texto = "📋 Agenda completa:\n\n"
    for dia in DIAS_VALIDOS:
        if dia not in MENSAJES_DIA:
            continue
        texto += f"{dia.upper()}:\n"
        for h, m, msg in sorted(MENSAJES_DIA[dia]):
            corto = (msg[:60] + "…") if len(msg) > 60 else msg
            texto += f"  {h:02d}:{m:02d} — {corto}\n"
        texto += "\n"
    await update.message.reply_text(texto)

async def recargar(update, context: ContextTypes.DEFAULT_TYPE):
    global _gc_cache
    _gc_cache = None   # forzar reconexión
    ok, err = cargar_agenda()
    if ok:
        dias = len(MENSAJES_DIA)
        total = sum(len(v) for v in MENSAJES_DIA.values())
        await update.message.reply_text(
            f"✅ Agenda recargada: {total} recordatorios en {dias} días.\n"
            "Los mensajes automáticos se actualizan al reiniciar el bot."
        )
    else:
        creds_set = "SI" if GOOGLE_CREDS_JSON else "NO"
        sheet_set = "SI" if SHEET_ID else "NO"
        await update.message.reply_text(
            f"❌ Error conectando con Google Sheets:\n\n{err}\n\n"
            f"GOOGLE_CREDENTIALS configurado: {creds_set}\n"
            f"SHEET_ID configurado: {sheet_set}"
        )

async def agregar(update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /agregar <dia> <hora> <minuto> <mensaje>"""
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /agregar <dia> <hora> <minuto> <mensaje>\n"
            f"Días válidos: {', '.join(DIAS_VALIDOS)}\n"
            "Ejemplo: /agregar lunes 10 0 Tomar medicación"
        )
        return
    dia = args[0].lower()
    if dia not in DIAS_VALIDOS:
        await update.message.reply_text(f"Día inválido. Usá uno de:\n{', '.join(DIAS_VALIDOS)}")
        return
    try:
        hora, minuto = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Hora y minuto deben ser números enteros.")
        return
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        await update.message.reply_text("Hora: 0-23. Minuto: 0-59.")
        return
    mensaje = " ".join(args[3:])
    try:
        get_worksheet("Agenda").append_row([dia, hora, minuto, mensaje])
        cargar_agenda()  # ignorar error, ya se guardó en Sheets
        await update.message.reply_text(
            f"✅ Recordatorio agregado:\n  {dia.capitalize()} {hora:02d}:{minuto:02d} — {mensaje}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar en Sheets: {e}")

async def borrar(update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /borrar <dia> <hora> <minuto>"""
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "Uso: /borrar <dia> <hora> <minuto>\n"
            "Ejemplo: /borrar lunes 10 0"
        )
        return
    dia = args[0].lower()
    try:
        hora, minuto = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Hora y minuto deben ser números.")
        return
    try:
        ws   = get_worksheet("Agenda")
        rows = ws.get_all_values()
        fila = next(
            (i + 2 for i, r in enumerate(rows[1:])
             if r[0].lower() == dia and str(r[1]) == str(hora) and str(r[2]) == str(minuto)),
            None
        )
        if fila is None:
            await update.message.reply_text(
                f"No encontré un recordatorio el {dia} a las {hora:02d}:{minuto:02d}.\n"
                "Usá /listar para ver los horarios exactos."
            )
            return
        ws.delete_rows(fila)
        cargar_agenda()
        await update.message.reply_text(f"🗑 Eliminado: {dia.capitalize()} {hora:02d}:{minuto:02d}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ─── COMPRAS COMMANDS ────────────────────────────────────────────
async def compra(update, context: ContextTypes.DEFAULT_TYPE):
    """
    Uso: /compra <producto> <cantidad> <precio_unitario> <supermercado> <billetera>
    Ejemplo: /compra leche 3 1500 Coto Ualá
    """
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "Uso:\n"
            "/compra <producto> <cantidad> <precio> <supermercado> <billetera>\n\n"
            "Ejemplo:\n"
            "/compra leche 3 1500 Coto Ualá\n\n"
            "Supermercados: Coto, Carrefour, Día\n"
            "Billeteras: MercadoPago, Brubank, Ualá, PersonalPay"
        )
        return

    producto     = args[0]
    supermercado = args[3]
    billetera    = args[4]

    try:
        cantidad    = float(args[1])
        precio_unit = float(args[2])
    except ValueError:
        await update.message.reply_text("Cantidad y precio deben ser números.\nEjemplo: /compra leche 3 1500 Coto Ualá")
        return

    fecha        = datetime.now(tz).strftime("%Y-%m-%d")
    precio_total = cantidad * precio_unit
    dia_es       = dia_hoy_es()

    descuento_row = next(
        (d for d in descuentos_del_dia(dia_es)
         if supermercado.lower() in str(d.get("supermercado", "")).lower()
         and billetera.lower() in str(d.get("billetera", "")).lower()),
        None
    )

    if descuento_row:
        pct          = float(descuento_row.get("porcentaje", 0))
        tope         = parsear_tope(descuento_row.get("tope"))
        ahorro_bruto = precio_total * pct / 100
        ahorro       = min(ahorro_bruto, tope) if tope else ahorro_bruto
        precio_final = precio_total - ahorro
        tope_aviso   = f" (tope ${tope:,.0f} — ahorro real ${ahorro:,.0f})" if tope and ahorro < ahorro_bruto else ""
    else:
        pct = ahorro = 0.0
        precio_final = precio_total
        tope_aviso   = ""

    try:
        get_worksheet("Historial").append_row([
            fecha, producto, cantidad, precio_unit, precio_total,
            supermercado, billetera, pct, round(ahorro, 2), round(precio_final, 2)
        ])
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar en Sheets: {e}")
        return

    if descuento_row:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} → ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Descuento {pct:g}%{tope_aviso} → ahorrás ${ahorro:,.0f}\n"
            f"  Total final: ${precio_final:,.0f} 💸"
        )
    else:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} → ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Sin descuento hoy para esa combinación.\n"
            f"  Usá /descuentos para ver las mejores opciones de hoy."
        )
    await update.message.reply_text(msg)


async def descuentos(update, context: ContextTypes.DEFAULT_TYPE):
    dia_es = dia_hoy_es()
    filas  = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(f"Sin descuentos registrados para hoy ({dia_es}).")
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    msg = f"💳 Descuentos del {dia_es}:\n\n"
    for d in filas_ord:
        tope      = parsear_tope(d.get("tope"))
        notas     = d.get("notas", "")
        tope_txt  = f" — tope ${tope:,.0f}" if tope else " — sin tope"
        notas_txt = f"\n   ⚠️ {notas}" if notas else ""
        msg += f"⭐ {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{tope_txt}{notas_txt}\n"
    await update.message.reply_text(msg)


async def donde(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /donde <producto>\n"
            "Ejemplo: /donde arroz\n"
            "Te digo qué super conviene hoy según los descuentos."
        )
        return
    producto  = " ".join(context.args)
    dia_es    = dia_hoy_es()
    filas     = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(f"No hay descuentos registrados para hoy ({dia_es}). Comprá donde quieras.")
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    mejor     = filas_ord[0]
    tope      = parsear_tope(mejor.get("tope"))
    notas     = mejor.get("notas", "")
    tope_txt  = f" — tope ${tope:,.0f}" if tope else " — sin tope"
    notas_txt = f"\n⚠️ {notas}" if notas else ""

    msg = f"🛒 Para {producto} hoy ({dia_es}):\n\n"
    msg += f"Mejor: {mejor['supermercado']} con {mejor['billetera']} → {mejor['porcentaje']:g}%{tope_txt}{notas_txt}\n"
    if len(filas_ord) > 1:
        msg += "\nOtras opciones:\n"
        for d in filas_ord[1:]:
            t     = parsear_tope(d.get("tope"))
            t_txt = f" — tope ${t:,.0f}" if t else " — sin tope"
            msg  += f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}\n"
    await update.message.reply_text(msg)


async def gastos(update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            mes = context.args[0]
            datetime.strptime(mes, "%Y-%m")
        except ValueError:
            await update.message.reply_text("Formato inválido. Usá: /gastos 2026-05")
            return
    else:
        mes = datetime.now(tz).strftime("%Y-%m")

    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer Historial: {e}")
        return

    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        await update.message.reply_text(
            f"Sin compras registradas en {mes}.\n"
            "Registrá compras con /compra."
        )
        return

    total_bruto  = sum(float(r.get("precio_total",  0)) for r in filas)
    total_ahorro = sum(float(r.get("ahorro",         0)) for r in filas)
    total_final  = sum(float(r.get("precio_final",   0)) for r in filas)

    por_super: dict = {}
    for r in filas:
        s = r.get("supermercado", "Otro")
        por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))

    msg = (
        f"📊 Gastos {mes}\n\n"
        f"  Compras: {len(filas)}\n"
        f"  Total sin descuentos: ${total_bruto:,.0f}\n"
        f"  Ahorro total: ${total_ahorro:,.0f}\n"
        f"  Total pagado: ${total_final:,.0f}\n\n"
        "Por supermercado:\n"
    )
    for s, monto in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
        msg += f"  {s}: ${monto:,.0f}\n"
    await update.message.reply_text(msg)


async def historial_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    n = 10
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        await update.message.reply_text(f"❌ Error al leer Historial: {e}")
        return

    if not rows:
        await update.message.reply_text("Sin compras registradas aún. Usá /compra para registrar.")
        return

    ultimas = rows[-n:][::-1]
    msg = f"🧾 Últimas {len(ultimas)} compras:\n\n"
    for r in ultimas:
        ahorro    = float(r.get("ahorro", 0))
        ahorro_txt = f" (−${ahorro:,.0f})" if ahorro > 0 else ""
        msg += (
            f"  {r.get('fecha','')} — {r.get('producto','')} x{r.get('cantidad','')}\n"
            f"  {r.get('supermercado','')} con {r.get('billetera','')} → "
            f"${float(r.get('precio_final',0)):,.0f}{ahorro_txt}\n\n"
        )
    await update.message.reply_text(msg)

async def evento(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /evento <fecha> <hora_inicio> <hora_fin> <título>\n"
            "Ejemplo: /evento 2026-05-10 14:00 16:00 Reunión Workana"
        )
        return
    fecha = args[0]
    inicio = f"{fecha}T{args[1]}:00"
    fin = f"{fecha}T{args[2]}:00"
    titulo = " ".join(args[3:])
    try:
        crear_evento(titulo, inicio, fin)
        await update.message.reply_text(
            f"✅ Evento creado: {titulo}\n📅 {fecha} {args[1]} - {args[2]}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ─── PAGOS COMMANDS ──────────────────────────────────────────────
async def pago(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "💳 PAGOS Y SUSCRIPCIONES\n\n"
            "/pago agregar <nombre> <dia> <monto> [categoria]\n"
            "/pago listar — Ver todos\n"
            "/pago borrar <nombre>\n"
            "/pago pagado <nombre> — Marcar como pagado este mes\n"
            "/pagos — Próximos vencimientos\n\n"
            "Ejemplo: /pago agregar Netflix 15 3200 streaming"
        )
        return
    sub = context.args[0].lower()
    if sub == "agregar":
        await pago_agregar(update, context)
    elif sub == "listar":
        await pago_listar(update, context)
    elif sub == "borrar":
        await pago_borrar(update, context)
    elif sub == "pagado":
        await pago_pagado(update, context)
    else:
        await update.message.reply_text("Subcomando no reconocido. Usá: agregar, listar, borrar, pagado")

async def pago_agregar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /pago agregar <nombre> <dia> <monto> [categoria]\n"
            "Ejemplo: /pago agregar Netflix 15 3200 streaming"
        )
        return
    nombre = args[1]
    try:
        dia_venc = int(args[2])
        monto = float(args[3])
    except ValueError:
        await update.message.reply_text("Día y monto deben ser números.")
        return
    if not (1 <= dia_venc <= 31):
        await update.message.reply_text("Día de vencimiento: 1 a 31.")
        return
    categoria = " ".join(args[4:]) if len(args) > 4 else ""
    try:
        get_worksheet_pagos().append_row([nombre, monto, dia_venc, categoria, "si", ""])
        await update.message.reply_text(f"✅ Pago agregado: {nombre} — ${monto:,.0f} el día {dia_venc}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pago_listar(update, context: ContextTypes.DEFAULT_TYPE):
    pagos = leer_pagos(solo_activos=False)
    if not pagos:
        await update.message.reply_text("No hay pagos registrados. Agregá uno con /pago agregar")
        return
    msg = "💳 Pagos y suscripciones:\n\n"
    for p in sorted(pagos, key=lambda r: int(r.get("dia_vencimiento", 0))):
        activo = "✅" if str(p.get("activo", "si")).lower() != "no" else "❌"
        mes_pagado = str(p.get("ultimo_mes", ""))
        estado = f" (pagado {mes_pagado})" if mes_pagado else ""
        cat = f" [{p.get('categoria', '')}]" if p.get("categoria") else ""
        monto = float(p.get("monto", 0))
        msg += f"{activo} {p['nombre']}{cat} — ${monto:,.0f} — vence día {p.get('dia_vencimiento','?')}{estado}\n"
    await update.message.reply_text(msg)

async def pago_borrar(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /pago borrar <nombre>")
        return
    nombre = " ".join(args[1:])
    try:
        ws = get_worksheet_pagos()
        rows = ws.get_all_values()
        fila = next((i+2 for i, r in enumerate(rows[1:]) if r[0].lower() == nombre.lower()), None)
        if fila is None:
            await update.message.reply_text(f"No encontré el pago '{nombre}'.")
            return
        ws.delete_rows(fila)
        await update.message.reply_text(f"🗑 Pago eliminado: {nombre}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pago_pagado(update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Uso: /pago pagado <nombre>")
        return
    nombre = " ".join(args[1:])
    mes_actual = datetime.now(tz).strftime("%Y-%m")
    try:
        ws = get_worksheet_pagos()
        rows = ws.get_all_values()
        fila = next((i+2 for i, r in enumerate(rows[1:]) if r[0].lower() == nombre.lower()), None)
        if fila is None:
            await update.message.reply_text(f"No encontré el pago '{nombre}'.")
            return
        ws.update(f"F{fila}", mes_actual)
        await update.message.reply_text(f"✅ {nombre} marcado como pagado ({mes_actual}).")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pagos_proximos_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    proximos = pagos_proximos()
    if not proximos:
        await update.message.reply_text("Ningún pago próximo a vencer. ¡Todo al día!")
        return
    msg = "📅 Próximos vencimientos:\n\n"
    for p in proximos:
        dias = p["dias_faltan"]
        icono = "🔴" if dias == 0 else "🟡" if dias <= 2 else "🟢"
        label = "HOY" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
        msg += f"{icono} {p['nombre']} — ${float(p.get('monto',0)):,.0f} — {label} (día {p.get('dia_vencimiento','?')})\n"
    await update.message.reply_text(msg)


# ─── AYUDA / START ───────────────────────────────────────────────
def texto_ayuda(nombre):
    return (
        f"👋 Hola {nombre}! Soy tu asistente personal.\n\n"
        "Tocá los botones fijos de abajo o hablame como quieras:\n\n"
        "• Agenda y recordatorios diarios\n"
        "• Pagos y suscripciones (vence X el día Y)\n"
        "• Compras con descuentos (compré X a $Y en Z con W)\n"
        "• Horas de trabajo freelance\n"
        "• Eventos en Google Calendar\n"
        "• Recordatorios puntuales (recordame X)\n\n"
        "También funcionan comandos: /hoy /listar /compra /evento /gastos /pagos /recargar /test /agenda /agregar /borrar /donde /descuentos /historial /pago /eliminar_evento"
    )

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    nombre = update.effective_user.first_name or "ahí"
    username = update.effective_user.username or "sin username"

    if chat_id == str(CHAT_ID):
        await update.message.reply_text(
            f"👋 ¡Hola {nombre}! Acá estoy para lo que necesites.\n\n"
            "Tocá los botones de abajo o escribime lo que quieras.\n"
            "Para ver todo lo que puedo hacer: /ayuda",
            reply_markup=TECLADO
        )

    elif chat_id == str(os.getenv("CHAT_ID_ESPOSA", "")):
        botones = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Ver eventos de hoy", callback_data="agenda_hoy")],
            [InlineKeyboardButton("📅 Ver eventos de mañana", callback_data="agenda_manana")],
            [InlineKeyboardButton("💳 Descuentos de hoy", callback_data="descuentos_hoy")],
        ])
        await update.message.reply_text(
            f"👋 Hola {nombre}!\n\n¿Qué querés hacer?",
            reply_markup=botones
        )

    else:
        await update.message.reply_text(
            f"👋 Hola {nombre}!\n\n"
            f"Este es un bot privado. Tu solicitud fue enviada al administrador."
        )
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"⚠️ Nueva persona intentó usar el bot:\n\n"
                 f"Nombre: {nombre}\n"
                 f"Username: @{username}\n"
                 f"Chat ID: `{chat_id}`",
            parse_mode="Markdown"
        )

async def callback_botones(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "agenda_hoy":
        dia_str = datetime.now(tz).strftime("%Y-%m-%d")
        dia_legible = datetime.now(tz).strftime("%d/%m/%Y")
        try:
            eventos = leer_eventos(dia_str)
            if not eventos:
                await query.edit_message_text(f"Sin eventos hoy ({dia_legible}).")
            else:
                msg = f"📅 Eventos del {dia_legible}:\n\n"
                for i, e in enumerate(eventos, 1):
                    hora = e["start"].get("dateTime", "")
                    hora = hora[11:16] if "T" in hora else "Todo el día"
                    msg += f"{i}. {hora} — {e.get('summary', 'Sin título')}\n"
                await query.edit_message_text(msg)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif query.data == "agenda_manana":
        from datetime import timedelta
        manana = datetime.now(tz) + timedelta(days=1)
        dia_str = manana.strftime("%Y-%m-%d")
        dia_legible = manana.strftime("%d/%m/%Y")
        try:
            eventos = leer_eventos(dia_str)
            if not eventos:
                await query.edit_message_text(f"Sin eventos mañana ({dia_legible}).")
            else:
                msg = f"📅 Eventos del {dia_legible}:\n\n"
                for i, e in enumerate(eventos, 1):
                    hora = e["start"].get("dateTime", "")
                    hora = hora[11:16] if "T" in hora else "Todo el día"
                    msg += f"{i}. {hora} — {e.get('summary', 'Sin título')}\n"
                await query.edit_message_text(msg)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif query.data == "descuentos_hoy":
        dia_es = dia_hoy_es()
        filas = descuentos_del_dia(dia_es)
        if not filas:
            await query.edit_message_text(f"Sin descuentos para hoy ({dia_es}).")
        else:
            filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
            msg = f"💳 Descuentos del {dia_es}:\n\n"
            for d in filas_ord:
                msg += f"⭐ {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%\n"
            await query.edit_message_text(msg)

async def ayuda(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTO_AYUDA)

async def test(update, context: ContextTypes.DEFAULT_TYPE):
    estado_agenda = f"{sum(len(v) for v in MENSAJES_DIA.values())} recordatorios cargados" \
                    if MENSAJES_DIA else "⚠️ agenda vacía — usá /recargar"
    await update.message.reply_text(f"✅ Bot funcionando.\n📋 Agenda: {estado_agenda}")


# ─── IA ──────────────────────────────────────────────────────────
def _build_system_prompt():
    ahora   = datetime.now(tz)
    dia_es  = dia_hoy_es()
    hora_actual = ahora.strftime("%H:%M")
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    return (
        "Sos el asistente personal de Francisco. Lo ayudás con su rutina diaria y sus compras.\n"
        "Llamalo siempre Francisco, nunca 'amigo' ni 'usuario'.\n\n"
        f"HOY ES {dia_es.upper()} {fecha_hoy}, SON LAS {hora_actual} (hora de Argentina).\n\n"
        "SUPERMERCADOS: Coto, Carrefour, Día.\n"
        "BILLETERAS: MercadoPago, Brubank, Ualá, PersonalPay, Supervielle, Banco Ciudad, Banco del Sol, Prex.\n\n"
        "Francisco es freelancer en Workana (desarrollo web). Vive con su esposa y su bebé.\n"
        "Tenés acceso a Google Calendar y Google Sheets de Francisco.\n"
        "Usá las herramientas para ver la agenda, descuentos, gastos, pagos, eventos y horas trabajadas.\n"
        "USÁ LAS HERRAMIENTAS. Cuando Francisco te pida hacer algo concreto, llamá la herramienta.\n"
        "No finjas que hiciste algo sin haber llamado la herramienta. Confirmá el resultado.\n"
        "Si Francisco dice 'agendame', 'anotame', 'creame un evento' → usá crear_evento_calendario.\n"
        "Si dice 'empiezo a trabajar en X' → usá iniciar_trabajo_tool.\n"
        "Si dice 'terminé', 'corté' → usá terminar_trabajo_tool.\n"
        "Si dice 'compré X a $Y en Z con W' → usá registrar_compra.\n"
        "Si dice 'agregá el pago de X' o 'X vence el día Y' → usá agregar_pago.\n"
        "Si dice 'recordame X' → usá agregar_recordatorio_puntual.\n"
        "NUNCA respondas 'listo' o 'agendado' sin haber llamado la herramienta.\n"
        "Si Francisco pregunta 'cómo viene mi día', 'qué tengo que hacer', consultá ver_agenda primero.\n"
        "Si pregunta por descuentos, gastos, pagos, horas trabajadas — consultá la herramienta primero.\n"
        "Botones rápidos que puede usar:\n"
        "  '📅 Hoy' → ver_agenda\n"
        "  '💳 Pagos' → ver_pagos\n"
        "  '🛒 Gastos' → ver_gastos\n"
        "  '⏱ Trabajo' → ver_horas_trabajadas\n"
        "  '📋 Tareas' → ver_recordatorios_pendientes\n"
        "  '📊 Resumen' → resumen_semanal_tool\n"
        "Respondé siempre en español, de forma cálida, natural y cercana, sin markdown ni asteriscos.\n"
        "No uses frases robóticas como 'en lenguaje natural' o 'asistente virtual'."
    )

historial_ia = {}  # chat_id -> list of messages
MAX_HISTORIAL = 12

def _get_historial(chat_id):
    cid = str(chat_id)
    if cid not in historial_ia:
        historial_ia[cid] = []
    h = historial_ia[cid]
    if len(h) > MAX_HISTORIAL:
        del h[:-MAX_HISTORIAL]
    return h

async def _ejecutar_herramienta(nombre, args):
    global _ultimos_eventos
    if nombre == "agregar_recordatorio":
        dia = args["dia"].lower()
        if dia not in DIAS_VALIDOS:
            return f"Día inválido: {dia}. Usá lunes a domingo."
        get_worksheet("Agenda").append_row([dia, args["hora"], args["minuto"], args["mensaje"]])
        cargar_agenda()
        return f"Recordatorio agregado: {dia} {args['hora']:02d}:{args['minuto']:02d} - {args['mensaje']}"

    elif nombre == "borrar_recordatorio":
        dia = args["dia"].lower()
        ws = get_worksheet("Agenda")
        rows = ws.get_all_values()
        fila = next(
            (i + 2 for i, r in enumerate(rows[1:])
             if r[0].lower() == dia and str(r[1]) == str(args["hora"]) and str(r[2]) == str(args["minuto"])),
            None
        )
        if fila is None:
            return f"No se encontró recordatorio el {dia} a las {args['hora']:02d}:{args['minuto']:02d}."
        ws.delete_rows(fila)
        cargar_agenda()
        return f"Recordatorio eliminado: {dia} {args['hora']:02d}:{args['minuto']:02d}"

    elif nombre == "registrar_compra":
        producto = args["producto"]
        cantidad = float(args["cantidad"])
        precio_unit = float(args["precio_unitario"])
        supermercado = args["supermercado"]
        billetera = args["billetera"]
        fecha = datetime.now(tz).strftime("%Y-%m-%d")
        precio_total = cantidad * precio_unit
        dia_es = dia_hoy_es()

        descuento_row = next(
            (d for d in descuentos_del_dia(dia_es)
             if supermercado.lower() in str(d.get("supermercado", "")).lower()
             and billetera.lower() in str(d.get("billetera", "")).lower()),
            None
        )
        pct = ahorro = 0.0
        tope_aviso = ""
        if descuento_row:
            pct = float(descuento_row.get("porcentaje", 0))
            tope = parsear_tope(descuento_row.get("tope"))
            ahorro_bruto = precio_total * pct / 100
            ahorro = min(ahorro_bruto, tope) if tope else ahorro_bruto
            tope_aviso = f" (tope ${tope:,.0f})" if tope and ahorro < ahorro_bruto else ""

        precio_final = precio_total - ahorro
        get_worksheet("Historial").append_row([
            fecha, producto, cantidad, precio_unit, precio_total,
            supermercado, billetera, pct, round(ahorro, 2), round(precio_final, 2)
        ])
        if descuento_row:
            return (
                f"Compra registrada: {producto} x{cantidad:g} a ${precio_unit:,.0f} c/u\n"
                f"Total bruto: ${precio_total:,.0f}\n"
                f"Descuento {supermercado}+{billetera}: {pct:g}%{tope_aviso}\n"
                f"Ahorro: ${ahorro:,.0f}\n"
                f"Total final: ${precio_final:,.0f}"
            )
        else:
            return (
                f"Compra registrada: {producto} x{cantidad:g} a ${precio_unit:,.0f} c/u\n"
                f"Total: ${precio_total:,.0f}\n"
                f"Sin descuento hoy para {supermercado}+{billetera}."
            )

    elif nombre == "agregar_pago":
        nombre_pago = args["nombre"]
        dia_venc = int(args["dia_vencimiento"])
        monto = float(args["monto"])
        categoria = args.get("categoria", "")
        if not (1 <= dia_venc <= 31):
            return f"Día de vencimiento inválido: {dia_venc}. Debe ser 1-31."
        get_worksheet_pagos().append_row([nombre_pago, monto, dia_venc, categoria, "si", ""])
        return f"Pago agregado: {nombre_pago} — ${monto:,.0f} vence el día {dia_venc} de cada mes."

    elif nombre == "marcar_pago_pagado":
        nombre_pago = args["nombre"]
        mes_actual = datetime.now(tz).strftime("%Y-%m")
        ws = get_worksheet_pagos()
        rows = ws.get_all_values()
        fila = next((i+2 for i, r in enumerate(rows[1:]) if r[0].lower() == nombre_pago.lower()), None)
        if fila is None:
            return f"No se encontró el pago '{nombre_pago}'."
        ws.update(f"F{fila}", mes_actual)
        return f"{nombre_pago} marcado como pagado ({mes_actual})."

    elif nombre == "ver_pagos":
        pagos = leer_pagos(solo_activos=False)
        if not pagos:
            return "No hay pagos registrados."
        lineas = ["Pagos y suscripciones:"]
        for p in sorted(pagos, key=lambda r: int(r.get("dia_vencimiento", 0))):
            activo = "✅" if str(p.get("activo", "si")).lower() != "no" else "❌"
            pagado = f" (pagado {p['ultimo_mes']})" if p.get("ultimo_mes") else ""
            lineas.append(f"{activo} {p['nombre']} — ${float(p.get('monto',0)):,.0f} — día {p.get('dia_vencimiento','?')}{pagado}")
        return "\n".join(lineas)

    elif nombre == "ver_gastos":
        mes = datetime.now(tz).strftime("%Y-%m")
        try:
            rows = get_worksheet("Historial").get_all_records()
        except:
            return "Error al leer el historial de compras."
        filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
        if not filas:
            return f"Sin compras en {mes}."
        total_bruto = sum(float(r.get("precio_total", 0)) for r in filas)
        total_ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
        total_final = sum(float(r.get("precio_final", 0)) for r in filas)
        por_super = {}
        for r in filas:
            s = r.get("supermercado", "Otro")
            por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))
        lineas = [
            f"Gastos {mes}:",
            f"  Compras: {len(filas)}",
            f"  Total bruto: ${total_bruto:,.0f}",
            f"  Ahorro: ${total_ahorro:,.0f}",
            f"  Total pagado: ${total_final:,.0f}",
            "Por supermercado:"
        ]
        for s, m in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
            lineas.append(f"  {s}: ${m:,.0f}")
        return "\n".join(lineas)

    elif nombre == "ver_descuentos":
        dia_es = dia_hoy_es()
        filas = descuentos_del_dia(dia_es)
        if not filas:
            return f"Sin descuentos registrados para hoy ({dia_es})."
        filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
        lineas = [f"Descuentos de hoy ({dia_es}):"]
        for d in filas_ord:
            t = parsear_tope(d.get("tope"))
            t_txt = f" (tope ${t:,.0f})" if t else ""
            lineas.append(f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}")
        return "\n".join(lineas)

    elif nombre == "ver_agenda":
        if not MENSAJES_DIA:
            return "La agenda está vacía."
        lineas = ["Agenda semanal:"]
        for dia in DIAS_VALIDOS:
            if dia not in MENSAJES_DIA:
                continue
            lineas.append(f"{dia.upper()}:")
            for h, m, msg in sorted(MENSAJES_DIA[dia]):
                lineas.append(f"  {h:02d}:{m:02d} — {msg}")
        return "\n".join(lineas)

    elif nombre == "crear_evento_calendario":
        fecha = args["fecha"]
        inicio = f"{fecha}T{args['hora_inicio']}:00"
        fin = f"{fecha}T{args['hora_fin']}:00"
        titulo = args["titulo"]
        crear_evento(titulo, inicio, fin)
        return f"Evento creado: {titulo} — {fecha} {args['hora_inicio']}-{args['hora_fin']}"

    elif nombre == "ver_eventos_calendario":
        from datetime import timedelta
        arg_fecha = args.get("fecha", "").lower()
        hoy = datetime.now(tz).date()
        if arg_fecha == "hoy":
            fecha_dt = hoy
        elif arg_fecha in ("mañana", "manana"):
            fecha_dt = hoy + timedelta(days=1)
        else:
            try:
                fecha_dt = datetime.strptime(arg_fecha, "%Y-%m-%d").date()
            except ValueError:
                return f"Fecha inválida: {arg_fecha}. Usá YYYY-MM-DD, 'hoy' o 'mañana'."
        dia_str = fecha_dt.strftime("%Y-%m-%d")
        try:
            eventos = leer_eventos(dia_str)
            _ultimos_eventos = eventos
            if not eventos:
                return f"No hay eventos para el {fecha_dt.strftime('%d/%m/%Y')}."
            lineas = [f"Eventos del {fecha_dt.strftime('%d/%m/%Y')}:"]
            for i, e in enumerate(eventos, 1):
                hora = e["start"].get("dateTime", e["start"].get("date", ""))
                hora = hora[11:16] if "T" in hora else "Todo el día"
                lineas.append(f"  {i}. {hora} — {e.get('summary', 'Sin título')}")
            return "\n".join(lineas)
        except Exception as e:
            return f"Error al leer eventos: {e}"

    elif nombre == "eliminar_evento_calendario":
        if not _ultimos_eventos:
            return "Primero consultá los eventos con ver_eventos_calendario."
        indice = int(args.get("indice", 1)) - 1
        if indice < 0 or indice >= len(_ultimos_eventos):
            return f"Número inválido. Hay {len(_ultimos_eventos)} eventos (usá 1 a {len(_ultimos_eventos)})."
        titulo = _ultimos_eventos[indice].get("summary", "Sin título")
        try:
            eliminar_evento(_ultimos_eventos[indice]["id"])
            _ultimos_eventos.pop(indice)
            return f"Evento eliminado: {titulo}"
        except Exception as e:
            return f"Error al eliminar: {e}"

    elif nombre == "iniciar_trabajo_tool":
        proyecto = args["proyecto"]
        descripcion = args.get("descripcion", "")
        return _iniciar_trabajo(proyecto, descripcion)

    elif nombre == "terminar_trabajo_tool":
        return _cerrar_sesion_trabajo()

    elif nombre == "ver_horas_trabajadas":
        horas, sesiones, por_proy = _calcular_horas()
        if horas == 0:
            return "No hay horas registradas este mes."
        lineas = [f"Horas trabajadas este mes: {horas:.1f}h total"]
        for proy, mins in por_proy.items():
            lineas.append(f"  {proy}: {mins / 60:.1f}h")
        return "\n".join(lineas)

    elif nombre == "agregar_recordatorio_puntual":
        texto = args["texto"]
        fecha = datetime.now(tz).strftime("%Y-%m-%d")
        get_worksheet_recordatorios().append_row([texto, fecha, "pendiente"])
        return f"Recordatorio agregado: {texto}"

    elif nombre == "ver_recordatorios_pendientes":
        pendientes = _leer_recordatorios_pendientes()
        if not pendientes:
            return "No hay recordatorios pendientes."
        lineas = ["Recordatorios pendientes:"]
        for i, r in enumerate(pendientes, 1):
            lineas.append(f"  {i}. {r['texto']} (desde {r.get('fecha_creacion','?')})")
        return "\n".join(lineas)

    elif nombre == "marcar_recordatorio_hecho":
        indice = int(args.get("indice", 1)) - 1
        pendientes = _leer_recordatorios_pendientes()
        if indice < 0 or indice >= len(pendientes):
            return f"Número inválido. Hay {len(pendientes)} pendientes (usá 1 a {len(pendientes)})."
        ws = get_worksheet_recordatorios()
        rows = ws.get_all_values()
        texto_buscado = pendientes[indice]["texto"]
        fila = next((i + 2 for i, r in enumerate(rows[1:]) if str(r[0]) == str(texto_buscado) and str(r[2]).lower() != "hecho"), None)
        if fila is None:
            return "No se pudo encontrar ese recordatorio."
        ws.update(f"C{fila}", "hecho")
        return f"Recordatorio marcado como hecho: {texto_buscado}"

    elif nombre == "resumen_semanal_tool":
        from datetime import timedelta
        hoy = datetime.now(tz).date()
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)
        lineas = [f"📊 Resumen {inicio.strftime('%d/%m')} al {fin.strftime('%d/%m')}\n"]

        try:
            rows = get_worksheet("Historial").get_all_records()
            filas = [r for r in rows if inicio.strftime("%Y-%m-%d") <= str(r.get("fecha", "")) <= fin.strftime("%Y-%m-%d")]
            if filas:
                total = sum(float(r.get("precio_final", 0)) for r in filas)
                ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
                lineas.append(f"💵 Gastos: {len(filas)} compras — ${total:,.0f} (ahorraste ${ahorro:,.0f})")
                por_super = {}
                for r in filas:
                    s = r.get("supermercado", "Otro")
                    por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))
                for s, m in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
                    lineas.append(f"  {s}: ${m:,.0f}")
            else:
                lineas.append("💵 Sin gastos esta semana")
        except Exception:
            pass

        horas, sesiones, por_proy = _calcular_horas()
        h_semana = sum(s["minutos"] / 60 for s in sesiones if inicio.strftime("%Y-%m-%d") <= s.get("fecha", "") <= fin.strftime("%Y-%m-%d"))
        if h_semana > 0:
            lineas.append(f"\n⏱ Trabajo: {h_semana:.1f}h")
            for p, mins in por_proy.items():
                lineas.append(f"  {p}: {mins / 60:.1f}h")

        prox = pagos_proximos(dias_ventana=5)
        if prox:
            lineas.append(f"\n🔴 Pagos próximos ({len(prox)}):")
            for p in prox[:4]:
                d = p["dias_faltan"]
                lbl = "HOY" if d == 0 else "mañana" if d == 1 else f"en {d} días"
                lineas.append(f"  {p['nombre']} — ${float(p.get('monto',0)):,.0f} — {lbl}")

        return "\n".join(lineas)

    return f"Herramienta desconocida: {nombre}"


async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    chat_id = str(update.effective_chat.id)
    h = _get_historial(chat_id)
    h.append({"role": "user", "content": texto})

    await update.message.chat.send_action("typing")

    mensajes_api = [{"role": "system", "content": _build_system_prompt()}] + h
    for _ in range(5):
        try:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=mensajes_api,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=500,
            )
        except Exception as e:
            await update.message.reply_text(f"Error al consultar la IA: {e}")
            return

        msg = response.choices[0].message
        logging.info(f"IA response: tool_calls={bool(msg.tool_calls)}, content={msg.content[:80] if msg.content else 'None'}")

        if not msg.tool_calls:
            respuesta = msg.content or "Listo."
            h.append({"role": "assistant", "content": respuesta})
            await update.message.reply_text(respuesta)
            return

        mensajes_api.append(msg)
        for tc in msg.tool_calls:
            nombre = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            logging.info(f"IA llamó herramienta: {nombre}({json.dumps(args, ensure_ascii=False)})")
            try:
                resultado = await _ejecutar_herramienta(nombre, args)
            except Exception as e:
                resultado = f"Error al ejecutar {nombre}: {e}"
                logging.error(f"Error en herramienta {nombre}: {e}", exc_info=True)
            mensajes_api.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": resultado
            })

    await update.message.reply_text("Hmm, hice varias cosas. ¿Necesitás algo más?")


# ─── MENSAJES PROGRAMADOS ────────────────────────────────────────
async def enviar_mensaje(bot, texto):
    await bot.send_message(chat_id=CHAT_ID, text=texto)

def programar_mensajes(scheduler, bot):
    dia_map = {"lunes":"mon","martes":"tue","miercoles":"wed",
               "jueves":"thu","viernes":"fri","sabado":"sat","domingo":"sun"}
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
    ok, err = cargar_agenda()
    if not ok:
        logging.warning(
            f"No se pudo cargar la agenda al inicio: {err}. "
            "Verificá GOOGLE_CREDENTIALS en las variables de entorno."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("ayuda",      ayuda))
    app.add_handler(CommandHandler("test",       test))
    app.add_handler(CommandHandler("hoy",        hoy))
    app.add_handler(CommandHandler("listar",     listar))
    app.add_handler(CommandHandler("agregar",    agregar))
    app.add_handler(CommandHandler("borrar",     borrar))
    app.add_handler(CommandHandler("recargar",   recargar))
    app.add_handler(CommandHandler("compra",     compra))
    app.add_handler(CommandHandler("donde",      donde))
    app.add_handler(CommandHandler("descuentos", descuentos))
    app.add_handler(CommandHandler("gastos",     gastos))
    app.add_handler(CommandHandler("evento",     evento))
    app.add_handler(CommandHandler("agenda", agenda_calendar))
    app.add_handler(CommandHandler("eliminar_evento", eliminar_evento_cmd))
    app.add_handler(CallbackQueryHandler(callback_botones))
    app.add_handler(CommandHandler("historial",  historial_cmd))
    app.add_handler(CommandHandler("pago",       pago))
    app.add_handler(CommandHandler("pagos",      pagos_proximos_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_ia))

    scheduler = AsyncIOScheduler()
    programar_mensajes(scheduler, app.bot)
    scheduler.add_job(
        notificar_pagos,
        CronTrigger(hour=9, minute=0, timezone=tz),
        args=[app.bot],
        id="notificar_pagos"
    )
    scheduler.add_job(
        notificar_recordatorios,
        CronTrigger(hour=9, minute=0, timezone=tz),
        args=[app.bot],
        id="notificar_recordatorios"
    )
    scheduler.add_job(
        enviar_resumen_semanal,
        CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=tz),
        args=[app.bot],
        id="resumen_semanal"
    )
    scheduler.start()

    logging.info("✅ Bot iniciado.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
