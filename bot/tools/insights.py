import logging
import random
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.sheets import get_worksheet
from bot.tools.trabajo import _calcular_horas
from bot.tools.habitos import _calcular_adherencia
from bot.tools.compras import descuentos_del_dia, dia_hoy_es

tz = pytz.timezone(settings.timezone)


async def generar_insights() -> str:
    lines = []

    # Insight de gastos por supermercado
    try:
        mes = datetime.now(tz).strftime("%Y-%m")
        rows = get_worksheet("Historial").get_all_records()
        filas = [r for r in rows if str(r.get("fecha", "")).startswith(mes)]
        por_super: dict[str, float] = {}
        for r in filas:
            s = str(r.get("supermercado", "Otro"))
            por_super[s] = por_super.get(s, 0) + float(r.get("precio_final", 0))

        if len(por_super) >= 2:
            supers = sorted(por_super.items(), key=lambda x: x[1], reverse=True)
            top = supers[0]
            bottom = supers[-1]
            ratio = top[1] / max(bottom[1], 1)
            if ratio > 1.5:
                lines.append(
                    f"💡 Este mes gastaste ${top[1]:,.0f} en {top[0]} "
                    f"y solo ${bottom[1]:,.0f} en {bottom[0]}. "
                    f"¿Probaste los descuentos de {bottom[0]}?"
                )
    except Exception:
        pass

    # Insight de proyectos
    try:
        hora_total, sesiones, por_proy = _calcular_horas()
        if len(por_proy) >= 2:
            proys = sorted(por_proy.items(), key=lambda x: x[1], reverse=True)
            top_p = proys[0]
            bottom_p = proys[-1]
            if top_p[1] > 0 and bottom_p[1] > 0:
                ratio_p = top_p[1] / max(bottom_p[1], 1)
                if ratio_p > 5:
                    lines.append(
                        f"💡 {top_p[0]}: {top_p[1]/60:.1f}h. "
                        f"{bottom_p[0]}: {bottom_p[1]/60:.1f}h. "
                        f"¿{bottom_p[0]} esta frenado o te olvidaste de registrar?"
                    )
    except Exception:
        pass

    # Insight de hábitos
    try:
        from bot.tools.habitos import WorksheetHabitos
        rows = WorksheetHabitos.get().get_all_records()
        habs = set(str(r.get("habito", "")).lower() for r in rows if r.get("habito"))
        mes_actual = datetime.now(tz).strftime("%Y-%m")
        mes_anterior = (datetime.now(tz).replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        for h in habs:
            pct_actual = _calcular_adherencia(h)
            if pct_actual < 40 and pct_actual > 0:
                lines.append(
                    f"💡 {h}: {pct_actual:.0f}% adherencia este mes. "
                    f"¿Ajustamos la meta o le metemos mas?"
                )
                break
    except Exception:
        pass

    if not lines:
        lines.append("💡 Todo viene equilibrado esta semana. ¡Bien ahi!")

    return "\n\n".join(lines)
