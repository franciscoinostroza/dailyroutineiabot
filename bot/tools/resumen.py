from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.calendar import leer_eventos
from bot.services.sheets import get_worksheet, WorksheetRecordatorios

from .compras import descuentos_del_dia
from .trabajo import _calcular_horas
from .pagos import ver_pagos

tz = pytz.timezone(settings.timezone)


def pagos_proximos(dias_ventana: int = 3) -> list[dict]:
    from bot.services.sheets import WorksheetPagos
    from calendar import monthrange

    hoy = datetime.now(tz)
    mes_actual = hoy.strftime("%Y-%m")
    pagos = WorksheetPagos.read_all(solo_activos=True)
    resultado = []
    for p in pagos:
        if str(p.get("ultimo_mes", "")) == mes_actual:
            continue
        dia_venc = int(p.get("dia_vencimiento", 0))
        if dia_venc <= 0:
            continue
        for offset in (0, 1):
            mes = hoy.month + offset
            ano = hoy.year
            if mes > 12:
                mes, ano = 1, ano + 1
            max_dia = monthrange(ano, mes)[1]
            dia = min(dia_venc, max_dia)
            fecha_venc = hoy.replace(year=ano, month=mes, day=dia)
            if fecha_venc.date() >= hoy.date():
                break
        else:
            continue
        dias_faltan = (fecha_venc.date() - hoy.date()).days
        if 0 <= dias_faltan <= dias_ventana:
            resultado.append({**p, "dias_faltan": dias_faltan})
    return sorted(resultado, key=lambda x: x["dias_faltan"])


async def _build_resumen(hoy: datetime) -> str:
    inicio = hoy.date() - timedelta(days=hoy.weekday())
    fin = inicio + timedelta(days=6)

    lineas = [f"📊 Resumen {inicio.strftime('%d/%m')} al {fin.strftime('%d/%m')}\n"]

    try:
        rows = get_worksheet("Historial").get_all_records()
        filas = [
            r for r in rows
            if inicio.strftime("%Y-%m-%d") <= str(r.get("fecha", "")) <= fin.strftime("%Y-%m-%d")
        ]
        if filas:
            total = sum(float(r.get("precio_final", 0)) for r in filas)
            ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
            lineas.append(f"💵 Gastos: {len(filas)} compras — ${total:,.0f} (ahorraste ${ahorro:,.0f})")
            por_super: dict[str, float] = {}
            for r in filas:
                s = str(r.get("supermercado", "Otro"))
                por_super[s] = por_super.get(s, 0.0) + float(r.get("precio_final", 0))
            for s, m in sorted(por_super.items(), key=lambda x: x[1], reverse=True):
                lineas.append(f"  {s}: ${m:,.0f}")
        else:
            lineas.append("💵 Sin gastos esta semana")
    except Exception:
        pass

    horas, sesiones, por_proy = _calcular_horas()
    h_semana = sum(
        s["minutos"] / 60 for s in sesiones
        if inicio.strftime("%Y-%m-%d") <= s.get("fecha", "") <= fin.strftime("%Y-%m-%d")
    )
    if h_semana > 0:
        lineas.append(f"\n⏱ Trabajo: {h_semana:.1f}h")
        for p, mins in por_proy.items():
            lineas.append(f"  {p}: {mins / 60:.1f}h")

    prox = pagos_proximos(dias_ventana=5)
    if prox:
        lineas.append(f"\n🔴 Pagos proximos ({len(prox)}):")
        for p in prox[:4]:
            d = p["dias_faltan"]
            lbl = "HOY" if d == 0 else "manana" if d == 1 else f"en {d} dias"
            lineas.append(f"  {p['nombre']} — ${float(p.get('monto', 0)):,.0f} — {lbl}")

    return "\n".join(lineas)


async def resumen_semanal_tool() -> str:
    hoy = datetime.now(tz)
    return await _build_resumen(hoy)


async def enviar_resumen_semanal(bot) -> None:
    import logging
    try:
        hoy = datetime.now(tz)
        inicio = hoy.date() - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)

        msg = f"📊 RESUMEN SEMANAL\n{inicio.strftime('%d/%m')} al {fin.strftime('%d/%m')}\n\n"

        try:
            rows = get_worksheet("Historial").get_all_records()
            filas = [
                r for r in rows
                if inicio.strftime("%Y-%m-%d") <= str(r.get("fecha", "")) <= fin.strftime("%Y-%m-%d")
            ]
            if filas:
                total = sum(float(r.get("precio_final", 0)) for r in filas)
                ahorro = sum(float(r.get("ahorro", 0)) for r in filas)
                msg += f"💵 Gastos: {len(filas)} compras — ${total:,.0f} (ahorraste ${ahorro:,.0f})\n"
            else:
                msg += "💵 Sin gastos esta semana\n"
        except Exception:
            msg += "💵 Sin gastos esta semana\n"

        horas, sesiones, por_proy = _calcular_horas()
        h_semana = sum(
            s["minutos"] / 60 for s in sesiones
            if inicio.strftime("%Y-%m-%d") <= s.get("fecha", "") <= fin.strftime("%Y-%m-%d")
        )
        if h_semana > 0:
            msg += f"⏱ Trabajo: {h_semana:.1f} horas\n"
            for proy, mins in por_proy.items():
                msg += f"  {proy}: {mins / 60:.1f}h\n"

        eventos = []
        for i in range(7):
            dia = inicio + timedelta(days=i)
            try:
                evs = leer_eventos(dia.strftime("%Y-%m-%d"))
                for e in evs:
                    eventos.append({
                        "fecha": dia.strftime("%d/%m"),
                        "titulo": e.get("summary", ""),
                    })
            except Exception:
                pass

        if eventos:
            msg += f"\n📅 Eventos de la semana ({len(eventos)}):\n"
            for e in eventos[:5]:
                msg += f"  {e['fecha']} — {e['titulo']}\n"

        prox = pagos_proximos(dias_ventana=5)
        if prox:
            msg += "\n🔴 Pagos proximos:\n"
            for p in prox[:3]:
                d = p["dias_faltan"]
                lbl = "HOY" if d == 0 else "manana" if d == 1 else f"en {d} dias"
                msg += f"  {p['nombre']} — {lbl}\n"

        pendientes = WorksheetRecordatorios.read_pending()
        if pendientes:
            msg += f"\n📋 {len(pendientes)} recordatorios pendientes"

        await bot.send_message(chat_id=settings.chat_id, text=msg)
    except Exception as e:
        logging.error(f"Error en resumen semanal: {e}", exc_info=True)


async def notificar_pagos(bot) -> None:
    import logging
    try:
        proximos = pagos_proximos(dias_ventana=settings.payments_reminder_window_days)
        if not proximos:
            return
        msg = "📅 Recordatorio de pagos:\n\n"
        for p in proximos:
            dias = p["dias_faltan"]
            icono = "🔴" if dias == 0 else "🟡" if dias <= 2 else "🟢"
            label = "HOY" if dias == 0 else "manana" if dias == 1 else f"en {dias} dias"
            msg += f"{icono} {p['nombre']} — ${float(p.get('monto', 0)):,.0f} — {label}\n"
        await bot.send_message(chat_id=settings.chat_id, text=msg)
        if settings.chat_id_esposa:
            await bot.send_message(chat_id=settings.chat_id_esposa, text=msg)
    except Exception as e:
        logging.error(f"Error en notificar_pagos: {e}")


async def notificar_recordatorios(bot) -> None:
    import logging
    try:
        pendientes = WorksheetRecordatorios.read_pending()
        if not pendientes:
            return
        msg = "📋 Recordatorios pendientes:\n\n"
        for i, r in enumerate(pendientes, 1):
            msg += f"{i}. {r['texto']}\n"
        msg += "\nHablame para marcarlos como hechos."
        await bot.send_message(chat_id=settings.chat_id, text=msg)
    except Exception as e:
        logging.error(f"Error en notificar_recordatorios: {e}")
