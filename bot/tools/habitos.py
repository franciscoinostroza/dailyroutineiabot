import logging
from datetime import datetime
import pytz

from bot.config import settings
from bot.services.sheets import get_or_create_worksheet

tz = pytz.timezone(settings.timezone)


class WorksheetHabitos:
    HEADERS = ["habito", "fecha", "hecho", "notas"]

    @staticmethod
    def get():
        return get_or_create_worksheet("Habitos", WorksheetHabitos.HEADERS, rows=200, cols=6)

    @staticmethod
    def read_month(habito: str, mes: str | None = None) -> list[dict]:
        if mes is None:
            mes = datetime.now(tz).strftime("%Y-%m")
        try:
            rows = WorksheetHabitos.get().get_all_records()
        except Exception as e:
            logging.error(f"Error leyendo Habitos: {e}")
            return []
        return [r for r in rows
                if str(r.get("habito", "")).lower() == habito.lower()
                and str(r.get("fecha", "")).startswith(mes)]

    @staticmethod
    def read_today(habito: str) -> dict | None:
        hoy = datetime.now(tz).strftime("%Y-%m-%d")
        try:
            rows = WorksheetHabitos.get().get_all_records()
        except Exception:
            return None
        for r in rows:
            if (str(r.get("habito", "")).lower() == habito.lower()
                    and str(r.get("fecha", "")) == hoy):
                return r
        return None

    @staticmethod
    def upsert(habito: str, hecho: str = "si", notas: str = ""):
        existing = WorksheetHabitos.read_today(habito)
        ws = WorksheetHabitos.get()
        if existing:
            rows = ws.get_all_values()
            for i, r in enumerate(rows[1:], start=2):
                if (r[0].lower() == habito.lower()
                        and str(r[2]) == "si"
                        and str(r[3]) == ""):
                    pass
        ws.append_row([habito, datetime.now(tz).strftime("%Y-%m-%d"), hecho, notas])


async def registrar_habito(habito: str, notas: str = "") -> str:
    habito_lower = habito.lower().strip()
    habito_clean = habito.strip()
    WorksheetHabitos.upsert(habito_clean, "si", notas)

    racha, racha_dias = _calcular_racha(habito_clean)
    pct = _calcular_adherencia(habito_clean)

    lines = [f"✅ {habito_clean} registrado"]
    if racha_dias >= 1:
        emoji = "🔥" if racha_dias >= 3 else "⭐" if racha_dias >= 1 else ""
        lines.append(f"{emoji} Racha: {racha_dias} dias seguidos")
    lines.append(f"📊 Adherencia este mes: {pct:.0f}%")
    if racha_dias >= 7:
        lines.append("🏆 ¡Record personal de racha!")
    return "\n".join(lines)


def _calcular_racha(habito: str) -> tuple[int, int]:
    from datetime import timedelta
    hoy = datetime.now(tz).date()
    mes = hoy.strftime("%Y-%m")
    registros = WorksheetHabitos.read_month(habito, mes)
    fechas = set()
    for r in registros:
        if str(r.get("hecho", "si")).lower() != "no":
            fechas.add(str(r.get("fecha", "")))

    racha = 0
    dia = hoy
    while dia.strftime("%Y-%m-%d") in fechas:
        racha += 1
        dia -= timedelta(days=1)
    return racha, racha


def _calcular_adherencia(habito: str) -> float:
    hoy = datetime.now(tz)
    mes = hoy.strftime("%Y-%m")
    dias_del_mes = hoy.day
    registros = WorksheetHabitos.read_month(habito, mes)
    dias_hecho = sum(1 for r in registros if str(r.get("hecho", "si")).lower() != "no"
                     and str(r.get("fecha", ""))[:7] == mes)
    return (dias_hecho / dias_del_mes * 100) if dias_del_mes > 0 else 0


async def ver_habitos() -> str:
    hoy = datetime.now(tz).strftime("%Y-%m")
    rows = WorksheetHabitos.get().get_all_records()
    if not rows:
        return "No hay habitos registrados. Decime 'hice ejercicio' o 'medite' para empezar."

    habs: dict[str, list] = {}
    for r in rows:
        h = str(r.get("habito", "")).lower()
        if h:
            habs.setdefault(h, []).append(r)

    lines = [f"🏃 Habitos — {datetime.now(tz).strftime('%B %Y').capitalize()}\n"]
    for nombre, regs in habs.items():
        racha, dias = _calcular_racha(nombre)
        pct = _calcular_adherencia(nombre)
        emoji = "🔥" if dias >= 3 else "💪"
        lines.append(f"{emoji} {nombre}: {pct:.0f}% — racha {dias}d")
    return "\n".join(lines)
