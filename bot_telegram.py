"""
BOT DE TELEGRAM - MI SISTEMA DE VIDA
=====================================
Requisitos:
  pip install python-telegram-bot==20.7 apscheduler pytz gspread google-auth

Configuración:
  1. Hablá con @BotFather y creá un bot → TOKEN
  2. Completá el .env con TOKEN, CHAT_ID, OPENAI_KEY, SHEET_ID, CREDENTIALS_FILE
  3. Ejecutá: python bot_telegram.py
"""

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

DIAS_VALIDOS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_SEMANA  = DIAS_VALIDOS
DIA_EN_ES    = {"monday":"lunes","tuesday":"martes","wednesday":"miercoles",
                "thursday":"jueves","friday":"viernes","saturday":"sabado","sunday":"domingo"}

# Datos de agenda (se cargan desde Google Sheets al iniciar)
MENSAJES_DIA: dict = {}
RESUMEN:      dict = {}


# ─── HELPERS SHEETS ──────────────────────────────────────────────
def get_spreadsheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds).open_by_key(SHEET_ID)

def get_worksheet(name="Agenda"):
    return get_spreadsheet().worksheet(name)

def dia_hoy_es():
    return DIA_EN_ES[datetime.now(tz).strftime("%A").lower()]

def es_ultimo_sabado():
    hoy = datetime.now(tz)
    if hoy.weekday() != 5:
        return False
    from calendar import monthrange
    ultimo_dia = monthrange(hoy.year, hoy.month)[1]
    return hoy.day + 7 > ultimo_dia

def parsear_tope(raw) -> float | None:
    if not raw or str(raw).strip().lower() in ("", "sin tope", "-"):
        return None
    nums = re.sub(r"[^\d]", "", str(raw))
    return float(nums) if nums else None

def descuentos_del_dia(dia_es: str) -> list[dict]:
    """Devuelve descuentos para el día dado, incluyendo sabado_ultimo si aplica."""
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


# ─── AGENDA ──────────────────────────────────────────────────────
def cargar_agenda():
    global MENSAJES_DIA, RESUMEN
    try:
        rows = get_worksheet("Agenda").get_all_records()
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
        RESUMEN      = resumen
        total = sum(len(v) for v in mensajes.values())
        logging.info(f"Agenda cargada: {total} mensajes en {len(mensajes)} días.")
        return True
    except Exception as e:
        logging.error(f"Error cargando agenda: {e}")
        return False


# ─── HANDLERS AGENDA ─────────────────────────────────────────────
async def hoy(update, context: ContextTypes.DEFAULT_TYPE):
    dia_es = dia_hoy_es()
    await update.message.reply_text(RESUMEN.get(dia_es, "No hay resumen para hoy."))

async def recargar(update, context: ContextTypes.DEFAULT_TYPE):
    ok = cargar_agenda()
    msg = "✅ Agenda recargada. Los recordatorios automáticos se actualizan al reiniciar." if ok \
          else "❌ Error al recargar la agenda."
    await update.message.reply_text(msg)

async def agregar(update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /agregar <dia> <hora> <minuto> <mensaje>"""
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Uso: /agregar <dia> <hora> <minuto> <mensaje>\n"
            "Ejemplo: /agregar lunes 10 0 Tomar medicación"
        )
        return
    dia = args[0].lower()
    if dia not in DIAS_VALIDOS:
        await update.message.reply_text(f"Día inválido. Usá: {', '.join(DIAS_VALIDOS)}")
        return
    try:
        hora, minuto = int(args[1]), int(args[2])
    except ValueError:
        await update.message.reply_text("Hora y minuto deben ser números.")
        return
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        await update.message.reply_text("Hora 0-23, minuto 0-59.")
        return
    mensaje = " ".join(args[3:])
    try:
        get_worksheet("Agenda").append_row([dia, hora, minuto, mensaje])
        cargar_agenda()
        await update.message.reply_text(
            f"✅ Recordatorio agregado:\n  {dia.capitalize()} {hora:02d}:{minuto:02d} — {mensaje}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def borrar(update, context: ContextTypes.DEFAULT_TYPE):
    """Uso: /borrar <dia> <hora> <minuto>"""
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Uso: /borrar <dia> <hora> <minuto>\nEjemplo: /borrar lunes 10 0")
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
            await update.message.reply_text(f"No encontré recordatorio el {dia} a las {hora:02d}:{minuto:02d}.")
            return
        ws.delete_rows(fila)
        cargar_agenda()
        await update.message.reply_text(f"🗑 Eliminado: {dia.capitalize()} {hora:02d}:{minuto:02d}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def listar(update, context: ContextTypes.DEFAULT_TYPE):
    if not MENSAJES_DIA:
        await update.message.reply_text("No hay recordatorios cargados.")
        return
    texto = "📋 Agenda completa:\n\n"
    for dia in DIAS_VALIDOS:
        if dia not in MENSAJES_DIA:
            continue
        texto += f"{dia.upper()}:\n"
        for h, m, msg in sorted(MENSAJES_DIA[dia]):
            resumen_msg = (msg[:55] + "...") if len(msg) > 55 else msg
            texto += f"  {h:02d}:{m:02d} — {resumen_msg}\n"
        texto += "\n"
    await update.message.reply_text(texto)


# ─── HANDLERS COMPRAS ────────────────────────────────────────────
async def compra(update, context: ContextTypes.DEFAULT_TYPE):
    """Registra una compra y aplica descuento si corresponde.
    Uso: /compra <producto> <cantidad> <precio_unitario> <supermercado> <billetera>
    Ejemplo: /compra leche 3 1500 Coto Ualá
    """
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "Uso: /compra <producto> <cantidad> <precio> <supermercado> <billetera>\n"
            "Ejemplo: /compra leche 3 1500 Coto Ualá"
        )
        return
    producto     = args[0]
    supermercado = args[3]
    billetera    = args[4]
    try:
        cantidad    = float(args[1])
        precio_unit = float(args[2])
    except ValueError:
        await update.message.reply_text("Cantidad y precio deben ser números.")
        return

    fecha        = datetime.now(tz).strftime("%Y-%m-%d")
    precio_total = cantidad * precio_unit
    dia_es       = dia_hoy_es()

    # Buscar descuento vigente para supermercado+billetera
    descuento_row = next(
        (d for d in descuentos_del_dia(dia_es)
         if supermercado.lower() in str(d.get("supermercado","")).lower()
         and billetera.lower() in str(d.get("billetera","")).lower()),
        None
    )

    if descuento_row:
        pct          = float(descuento_row.get("porcentaje", 0))
        tope         = parsear_tope(descuento_row.get("tope"))
        ahorro_bruto = precio_total * pct / 100
        ahorro       = min(ahorro_bruto, tope) if tope else ahorro_bruto
        precio_final = precio_total - ahorro
        tope_aviso   = f" (tope ${tope:,.0f})" if tope and ahorro < ahorro_bruto else ""
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
        await update.message.reply_text(f"❌ Error al guardar: {e}")
        return

    if descuento_row:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} — ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Descuento: {pct:g}%{tope_aviso} → ahorrás ${ahorro:,.0f}\n"
            f"  Total final: ${precio_final:,.0f} 💸"
        )
    else:
        msg = (
            f"✅ Compra registrada\n"
            f"  {producto} x{cantidad:g} — ${precio_total:,.0f}\n"
            f"  {supermercado} con {billetera}\n"
            f"  Sin descuento hoy para esa combinación.\n"
            f"  Usá /descuentos para ver las mejores opciones."
        )
    await update.message.reply_text(msg)


async def descuentos(update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los descuentos vigentes para hoy."""
    dia_es  = dia_hoy_es()
    filas   = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(f"No hay descuentos registrados para hoy ({dia_es}).")
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    msg = f"💳 Descuentos del {dia_es}:\n\n"
    for d in filas_ord:
        tope  = parsear_tope(d.get("tope"))
        notas = d.get("notas", "")
        tope_txt  = f" — tope ${tope:,.0f}" if tope else " — sin tope"
        notas_txt = f"\n   ⚠️ {notas}" if notas else ""
        msg += f"⭐ {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{tope_txt}{notas_txt}\n"
    await update.message.reply_text(msg)


async def donde(update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra dónde conviene comprar hoy según descuentos.
    Uso: /donde <producto>
    """
    if not context.args:
        await update.message.reply_text("Uso: /donde <producto>\nEjemplo: /donde leche")
        return
    producto = " ".join(context.args)
    dia_es   = dia_hoy_es()
    filas    = descuentos_del_dia(dia_es)

    if not filas:
        await update.message.reply_text(f"No hay descuentos hoy ({dia_es}). Comprá donde quieras.")
        return

    filas_ord = sorted(filas, key=lambda r: float(r.get("porcentaje", 0)), reverse=True)
    mejor     = filas_ord[0]
    tope      = parsear_tope(mejor.get("tope"))
    tope_txt  = f" — tope ${tope:,.0f}" if tope else " — sin tope"
    notas     = mejor.get("notas", "")
    notas_txt = f"\n⚠️ {notas}" if notas else ""

    msg = f"🛒 Para comprar {producto} hoy ({dia_es}):\n\n"
    msg += f"Mejor opción: {mejor['supermercado']} con {mejor['billetera']} → {mejor['porcentaje']:g}%{tope_txt}{notas_txt}\n\n"

    if len(filas_ord) > 1:
        msg += "Otras opciones:\n"
        for d in filas_ord[1:]:
            t     = parsear_tope(d.get("tope"))
            t_txt = f" — tope ${t:,.0f}" if t else " — sin tope"
            msg  += f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}\n"

    await update.message.reply_text(msg)


async def gastos(update, context: ContextTypes.DEFAULT_TYPE):
    """Analiza gastos del mes actual o el indicado.
    Uso: /gastos [YYYY-MM]
    """
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
        await update.message.reply_text(f"❌ Error al leer historial: {e}")
        return

    filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
    if not filas:
        await update.message.reply_text(f"Sin compras registradas en {mes}.")
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
        f"  Compras registradas: {len(filas)}\n"
        f"  Subtotal sin descuentos: ${total_bruto:,.0f}\n"
        f"  Ahorro total: ${total_ahorro:,.0f}\n"
        f"  Total pagado: ${total_final:,.0f}\n\n"
        f"Por supermercado:\n"
    )
    for s, monto in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
        msg += f"  {s}: ${monto:,.0f}\n"

    await update.message.reply_text(msg)


async def historial_cmd(update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las últimas N compras. Uso: /historial [N]"""
    n = 10
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass

    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return

    if not rows:
        await update.message.reply_text("No hay compras registradas aún.")
        return

    ultimas = rows[-n:][::-1]
    msg = f"🧾 Últimas {len(ultimas)} compras:\n\n"
    for r in ultimas:
        ahorro = float(r.get("ahorro", 0))
        ahorro_txt = f" (−${ahorro:,.0f})" if ahorro > 0 else ""
        msg += (
            f"  {r.get('fecha','')} — {r.get('producto','')} x{r.get('cantidad','')}\n"
            f"  {r.get('supermercado','')} con {r.get('billetera','')} → "
            f"${float(r.get('precio_final',0)):,.0f}{ahorro_txt}\n\n"
        )
    await update.message.reply_text(msg)


# ─── HANDLERS GENERALES ──────────────────────────────────────────
TEXTO_AYUDA = (
    "👋 Hola Francisco! Soy tu asistente personal.\n\n"

    "📅 AGENDA\n"
    "/hoy — Resumen del día actual\n"
    "/listar — Ver toda la agenda semanal\n"
    "/agregar <dia> <hora> <min> <mensaje>\n"
    "   Ejemplo: /agregar lunes 10 0 Tomar medicación\n"
    "/borrar <dia> <hora> <min>\n"
    "   Ejemplo: /borrar lunes 10 0\n"
    "/recargar — Recargar agenda desde Google Sheets\n\n"

    "🛒 COMPRAS\n"
    "/compra <producto> <cantidad> <precio> <super> <billetera>\n"
    "   Ejemplo: /compra leche 3 1500 Coto Ualá\n"
    "   → Registra la compra y aplica descuento automático si corresponde\n"
    "/donde <producto>\n"
    "   Ejemplo: /donde arroz\n"
    "   → Muestra el mejor super hoy según descuentos vigentes\n"
    "/descuentos — Ver todos los descuentos vigentes hoy\n"
    "/gastos [YYYY-MM]\n"
    "   Ejemplo: /gastos 2026-05\n"
    "   → Total gastado, ahorro y desglose por super del mes\n"
    "/historial [N]\n"
    "   Ejemplo: /historial 20\n"
    "   → Últimas N compras registradas (por defecto 10)\n\n"

    "💳 DESCUENTOS DISPONIBLES\n"
    "Lunes    → Coto con Ualá 25% (tope $15.000/mes)\n"
    "Miércoles→ Día con Mercado Pago 10% (QR, sin tope)\n"
    "Jueves   → Coto con Brubank 30% ⭐\n"
    "           Carrefour con Mercado Pago 15% (QR)\n"
    "           Día con Personal Pay 20%\n"
    "Viernes  → Coto con Mercado Pago 25% (QR, excluye carnes/verduras)\n"
    "Sábado   → Carrefour con Mercado Pago 10% (QR)\n"
    "Último sáb → Carrefour con Ualá 20% (tope $10.000)\n"
    "Domingo  → Carrefour con Mercado Pago 10% (QR)\n\n"

    "🤖 IA\n"
    "Escribime cualquier cosa sin usar / y te respondo en base a tu\n"
    "agenda, tus descuentos y tu contexto personal. Por ejemplo:\n"
    "  • ¿Qué debería estar haciendo ahora?\n"
    "  • ¿Dónde me conviene hacer las compras esta semana?\n"
    "  • ¿Cuánto ahorré este mes?\n"
)

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTO_AYUDA)

async def test(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando.")

async def ayuda(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTO_AYUDA)


# ─── IA ──────────────────────────────────────────────────────────
def _build_system_prompt():
    ahora      = datetime.now(tz)
    dia_es     = dia_hoy_es()
    hora_actual = ahora.strftime("%H:%M")

    agenda_txt = ""
    for d in DIAS_SEMANA:
        msgs = "\n".join(f"    {h:02d}:{m:02d} — {t}" for h, m, t in MENSAJES_DIA.get(d, []))
        agenda_txt += f"\n{d.upper()}:\n{msgs}\n"

    descuentos_txt = ""
    try:
        filas = descuentos_del_dia(dia_es)
        if filas:
            for d in sorted(filas, key=lambda r: float(r.get("porcentaje",0)), reverse=True):
                t = parsear_tope(d.get("tope"))
                t_txt = f" tope ${t:,.0f}" if t else " sin tope"
                descuentos_txt += f"  {d['supermercado']} con {d['billetera']}: {d['porcentaje']:g}%{t_txt}\n"
    except Exception:
        pass

    return (
        "Sos el asistente personal de Francisco. Lo ayudás con su rutina diaria y sus compras.\n"
        "Cuando te dirijas a él, llamalo Francisco.\n\n"
        f"HOY ES {dia_es.upper()}, SON LAS {hora_actual}.\n\n"
        f"AGENDA:\n{agenda_txt}\n"
        f"DESCUENTOS HOY:\n{descuentos_txt if descuentos_txt else '  Ninguno registrado.'}\n\n"
        "SUPERMERCADOS: Coto, Carrefour, Día.\n"
        "BILLETERAS: Mercado Pago, Brubank, Ualá, Personal Pay, Supervielle, Banco Ciudad, Banco del Sol, Prex.\n\n"
        "Respondé siempre en español, de forma cálida y natural, sin markdown ni asteriscos.\n"
        "No inventes información que no esté en la agenda o los descuentos."
    )

historial    = []
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
            messages=[{"role": "system", "content": _build_system_prompt()}, *historial],
            max_tokens=500,
        )
        respuesta = response.choices[0].message.content
        historial.append({"role": "assistant", "content": respuesta})
        if len(historial) > MAX_HISTORIAL:
            del historial[:-MAX_HISTORIAL]
    except Exception as e:
        respuesta = f"Error al consultar la IA: {e}"
    await update.message.reply_text(respuesta)


# ─── MENSAJES PROGRAMADOS ────────────────────────────────────────
async def enviar_mensaje(bot, texto):
    historial.append({"role": "assistant", "content": texto})
    if len(historial) > MAX_HISTORIAL:
        del historial[:-MAX_HISTORIAL]
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
    cargar_agenda()

    app = Application.builder().token(TOKEN).build()

    # Agenda
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("ayuda",     ayuda))
    app.add_handler(CommandHandler("test",      test))
    app.add_handler(CommandHandler("hoy",       hoy))
    app.add_handler(CommandHandler("listar",    listar))
    app.add_handler(CommandHandler("agregar",   agregar))
    app.add_handler(CommandHandler("borrar",    borrar))
    app.add_handler(CommandHandler("recargar",  recargar))

    # Compras
    app.add_handler(CommandHandler("compra",    compra))
    app.add_handler(CommandHandler("donde",     donde))
    app.add_handler(CommandHandler("descuentos",descuentos))
    app.add_handler(CommandHandler("gastos",    gastos))
    app.add_handler(CommandHandler("historial", historial_cmd))

    # IA
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_ia))

    scheduler = AsyncIOScheduler()
    programar_mensajes(scheduler, app.bot)
    scheduler.start()

    print("✅ Bot iniciado.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
