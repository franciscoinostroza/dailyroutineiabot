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
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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
async def agenda_calendar(update, context: ContextTypes.DEFAULT_TYPE):
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
        if not eventos:
            await update.message.reply_text(f"Sin eventos en el calendario para el {dia_legible}.")
            return
        msg = f"📅 Eventos del {dia_legible}:\n\n"
        for e in eventos:
            hora = e["start"].get("dateTime", e["start"].get("date", ""))
            if "T" in hora:
                hora = hora[11:16]
            else:
                hora = "Todo el día"
            msg += f"• {hora} — {e.get('summary', 'Sin título')}\n"
        await update.message.reply_text(msg)
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

# ─── AYUDA / START ───────────────────────────────────────────────
TEXTO_AYUDA = (
    "👋 Hola Francisco! Soy tu asistente personal.\n\n"
    "📅 AGENDA\n"
    "/hoy — Resumen del día\n"
    "/listar — Toda la agenda semanal\n"
    "/agregar lunes 10 0 Tomar medicación\n"
    "/borrar lunes 10 0\n"
    "/recargar — Sincronizar desde Google Sheets\n\n"
    "🗓 GOOGLE CALENDAR\n"
    "/evento 2026-05-06 10:00 11:00 Reunión\n"
    "/agenda hoy — Eventos de hoy\n"
    "/agenda mañana — Eventos de mañana\n"
    "/agenda lunes — Eventos del próximo lunes\n"
    "/agenda 06/05 — Eventos de una fecha específica\n\n"
    "🛒 COMPRAS\n"
    "/compra leche 3 1500 Coto Ualá\n"
    "/donde arroz — Mejor super hoy\n"
    "/descuentos — Descuentos vigentes hoy\n"
    "/gastos — Resumen del mes\n"
    "/gastos 2026-04 — Mes específico\n"
    "/historial — Últimas 10 compras\n"
    "/historial 20 — Últimas 20\n\n"
    "💳 DESCUENTOS MAYO 2026\n"
    "Lun → Coto con Ualá 25%\n"
    "Mié → Día con MercadoPago 10%\n"
    "Jue → Coto con Brubank 30% ⭐\n"
    "     Carrefour con MercadoPago 15%\n"
    "     Día con PersonalPay 20%\n"
    "Vie → Coto con MercadoPago 25%\n"
    "Sáb → Carrefour con MercadoPago 10%\n"
    "Último sáb → Carrefour con Ualá 20%\n"
    "Dom → Carrefour con MercadoPago 10%\n\n"
    "🤖 IA\n"
    "Escribime sin / para hablar con la IA.\n"
    "Ej: ¿Qué debería hacer ahora?\n"
    "    ¿Dónde compro esta semana?\n"
    "    ¿Qué eventos tengo mañana?"
)

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTO_AYUDA)

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
        "Tenés acceso a Google Calendar de Francisco para crear eventos con el comando /evento.\n"
        "Tenés acceso a busquedas en la web"
        "Tenés acceso a Google Sheets con su agenda, descuentos e historial de compras.\n"
        "Respondé siempre en español, de forma cálida y natural, sin markdown ni asteriscos.\n"
        "No inventes información que no esté en la agenda o los descuentos."
    )

historial_ia  = []
MAX_HISTORIAL = 30

async def responder_ia(update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    historial_ia.append({"role": "user", "content": texto})
    if len(historial_ia) > MAX_HISTORIAL:
        del historial_ia[:-MAX_HISTORIAL]
    await update.message.chat.send_action("typing")
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": _build_system_prompt()}, *historial_ia],
            max_tokens=500,
        )
        respuesta = response.choices[0].message.content
        historial_ia.append({"role": "assistant", "content": respuesta})
        if len(historial_ia) > MAX_HISTORIAL:
            del historial_ia[:-MAX_HISTORIAL]
    except Exception as e:
        respuesta = f"Error al consultar la IA: {e}"
    await update.message.reply_text(respuesta)


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
    app.add_handler(CommandHandler("historial",  historial_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_ia))

    scheduler = AsyncIOScheduler()
    programar_mensajes(scheduler, app.bot)
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
