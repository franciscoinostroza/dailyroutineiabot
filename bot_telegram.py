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
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
            "description": "Crea un evento en Google Calendar de Francisco",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "YYYY-MM-DD"},
                    "hora_inicio": {"type": "string", "description": "HH:MM"},
                    "hora_fin": {"type": "string", "description": "HH:MM"},
                    "titulo": {"type": "string"}
                },
                "required": ["fecha", "hora_inicio", "hora_fin", "titulo"]
            }
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
    evento = {
        "summary": titulo,
        "description": descripcion,
        "start": {"dateTime": inicio, "timeZone": TIMEZONE},
        "end": {"dateTime": fin, "timeZone": TIMEZONE},
    }
    return service.events().insert(calendarId=os.getenv("CALENDAR_ID", "primary"), body=evento).execute()

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
        f"👋 Hola {nombre}!\n\n"
        "📅 AGENDA\n"
        "/hoy — Resumen del día\n"
        "/listar — Agenda semanal completa\n"
        "/agregar lunes 10 0 Texto\n"
        "/borrar lunes 10 0\n"
        "/recargar — Sincronizar con Sheets\n\n"
        "🗓 CALENDAR\n"
        "/evento 2026-05-06 10:00 11:00 Título\n"
        "/agenda hoy — Eventos de hoy\n"
        "/agenda mañana — Eventos de mañana\n"
        "/agenda lunes — Próximo lunes\n"
        "/eliminar_evento 1 — Eliminar evento\n\n"
        "💳 PAGOS\n"
        "/pago agregar Netflix 15 3200\n"
        "/pago listar — Ver todos\n"
        "/pago pagado Netflix\n"
        "/pagos — Próximos vencimientos\n"
        "/pago borrar Netflix\n\n"
        "🛒 COMPRAS\n"
        "/compra leche 3 1500 Coto Ualá\n"
        "/donde arroz — Mejor super hoy\n"
        "/descuentos — Descuentos de hoy\n"
        "/gastos — Resumen del mes\n"
        "/historial — Últimas compras\n\n"
        "🤖 IA\n"
        "Escribime cualquier cosa sin /\n"
    )

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    nombre = update.effective_user.first_name or "ahí"
    username = update.effective_user.username or "sin username"

    if chat_id == str(CHAT_ID):
        await update.message.reply_text(texto_ayuda(nombre))

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

    agenda_txt = ""
    if MENSAJES_DIA:
        for d in DIAS_SEMANA:
            msgs = "\n".join(f"    {h:02d}:{m:02d} — {t}" for h, m, t in MENSAJES_DIA.get(d, []))
            agenda_txt += f"\n{d.upper()}:\n{msgs}\n"
    else:
        agenda_txt = "\n  (No disponible — error de conexión con Google Sheets)\n"

    descuentos_txt = ""
    try:
        filas = descuentos_del_dia(dia_es)
        if filas:
            for d in sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True):
                t     = parsear_tope(d.get("tope"))
                t_txt = f" tope ${t:,.0f}" if t else " sin tope"
                descuentos_txt += f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}\n"
        else:
            descuentos_txt = "  Ninguno para hoy.\n"
    except Exception:
        descuentos_txt = "  (No disponible)\n"

    return (
        "Sos el asistente personal de Francisco. Lo ayudás con su rutina diaria y sus compras.\n"
        "Llamalo siempre Francisco, nunca 'amigo' ni 'usuario'.\n\n"
        f"HOY ES {dia_es.upper()}, SON LAS {hora_actual}.\n\n"
        f"SU AGENDA:\n{agenda_txt}\n"
        f"DESCUENTOS HOY:\n{descuentos_txt}\n"
        "SUPERMERCADOS: Coto, Carrefour, Día.\n"
        "BILLETERAS: MercadoPago, Brubank, Ualá, PersonalPay, Supervielle, Banco Ciudad, Banco del Sol, Prex.\n\n"
        "Francisco es freelancer en Workana (desarrollo web). Vive con su esposa y su bebé.\n"
        "Tenés acceso a Google Calendar y Google Sheets de Francisco.\n"
        "Podés usar herramientas para: agregar/quitar recordatorios, registrar compras con descuentos,\n"
        "agregar pagos/suscripciones, marcar pagos como pagados, ver agenda/descuentos/gastos/pagos,\n"
        "y crear eventos en el calendario.\n"
        "Siempre que Francisco te pida hacer algo, usá la herramienta correspondiente sin pedir confirmación.\n"
        "Después de ejecutar una herramienta, confirmá brevemente lo que hiciste.\n"
        "Respondé siempre en español, de forma cálida y natural, sin markdown ni asteriscos."
    )

historial_ia  = []
MAX_HISTORIAL = 30

async def _ejecutar_herramienta(nombre, args):
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

    return f"Herramienta desconocida: {nombre}"


async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    historial_ia.append({"role": "user", "content": texto})
    if len(historial_ia) > MAX_HISTORIAL:
        del historial_ia[:-MAX_HISTORIAL]
    await update.message.chat.send_action("typing")

    mensajes_api = [{"role": "system", "content": _build_system_prompt()}] + historial_ia
    for _ in range(5):  # máximo 5 iteraciones de tool calls
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

        if not msg.tool_calls:
            respuesta = msg.content or "Listo."
            historial_ia.append({"role": "assistant", "content": respuesta})
            if len(historial_ia) > MAX_HISTORIAL:
                del historial_ia[:-MAX_HISTORIAL]
            await update.message.reply_text(respuesta)
            return

        mensajes_api.append(msg)
        for tc in msg.tool_calls:
            nombre = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            resultado = await _ejecutar_herramienta(nombre, args)
            mensajes_api.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": resultado
            })

    await update.message.reply_text("Hmm, hice varias cosas. ¿Necesitás algo más?")


# ─── MENSAJES PROGRAMADOS ────────────────────────────────────────
async def enviar_mensaje(bot, texto):
    historial_ia.append({"role": "assistant", "content": texto})
    if len(historial_ia) > MAX_HISTORIAL:
        del historial_ia[:-MAX_HISTORIAL]
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
