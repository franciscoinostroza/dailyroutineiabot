import io
import logging
from datetime import datetime, timedelta
import pytz

from bot.config import settings
from bot.services.sheets import get_worksheet
from bot.tools.trabajo import _calcular_horas

tz = pytz.timezone(settings.timezone)


async def generar_grafico_gastos(meses: int = 3) -> io.BytesIO | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    hoy = datetime.now(tz)
    try:
        rows = get_worksheet("Historial").get_all_records()
    except Exception:
        return None

    if not rows:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Gráfico 1: gastos mensuales
    gastos_mensuales: dict[str, float] = {}
    for r in rows:
        fecha_str = str(r.get("fecha", ""))
        if not fecha_str:
            continue
        try:
            mes_key = fecha_str[:7]
            gastos_mensuales[mes_key] = gastos_mensuales.get(mes_key, 0) + float(r.get("precio_final", 0))
        except Exception:
            pass

    meses_keys = sorted(gastos_mensuales.keys())[-meses:]
    valores = [gastos_mensuales[m] for m in meses_keys]

    ax1.bar(meses_keys, valores, color="#4CAF50", edgecolor="#2E7D32")
    ax1.set_title("Gastos mensuales", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Total ($)")
    for i, v in enumerate(valores):
        ax1.text(i, v + max(valores) * 0.02, f"${v:,.0f}", ha="center", fontsize=9)

    # Gráfico 2: distribución por supermercado (mes actual)
    mes_actual = hoy.strftime("%Y-%m")
    por_super: dict[str, float] = {}
    for r in rows:
        if not str(r.get("fecha", "")).startswith(mes_actual):
            continue
        s = str(r.get("supermercado", "Otro"))
        por_super[s] = por_super.get(s, 0) + float(r.get("precio_final", 0))

    if por_super:
        labels = list(por_super.keys())
        sizes = list(por_super.values())
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]
        ax2.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors[:len(labels)],
                startangle=90, textprops={"fontsize": 8})
        ax2.set_title(f"Distribucion por supermercado - {mes_actual}", fontsize=14, fontweight="bold")
    else:
        ax2.text(0.5, 0.5, "Sin datos este mes", ha="center", va="center", transform=ax2.transAxes, fontsize=14)

    plt.tight_layout(pad=3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


async def generar_grafico_trabajo(meses: int = 3) -> io.BytesIO | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    horas, sesiones, por_proy = _calcular_horas()

    if not sesiones:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))

    proyectos = list(por_proy.keys())
    horas_vals = [por_proy[p] / 60 for p in proyectos]

    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
    bars = ax.barh(proyectos, horas_vals, color=colors[:len(proyectos)], edgecolor="#333")

    for bar, val in zip(bars, horas_vals):
        ax.text(bar.get_width() + max(horas_vals) * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}h", va="center", fontsize=10, fontweight="bold")

    ax.set_title(f"Horas trabajadas este mes: {horas:.1f}h total", fontsize=14, fontweight="bold")
    ax.set_xlabel("Horas")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
