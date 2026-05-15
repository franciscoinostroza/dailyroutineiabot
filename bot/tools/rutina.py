import logging
from bot.config import settings
from bot.services.sheets import get_worksheet


DIAS_VALIDOS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

MENSAJES_DIA: dict = {}
RESUMEN: dict = {}


def cargar_agenda() -> tuple[bool, str | None]:
    global MENSAJES_DIA, RESUMEN
    try:
        rows = get_worksheet("Agenda").get_all_records()
        mensajes = {}
        for row in rows:
            dia = str(row["dia"]).strip().lower()
            hora = int(row["hora"])
            minuto = int(row["minuto"])
            msg = str(row["mensaje"])
            mensajes.setdefault(dia, []).append((hora, minuto, msg))
        resumen = {}
        for dia, lista in mensajes.items():
            for h, m, txt in lista:
                if h == 6 and m == 0:
                    resumen[dia] = txt
                    break
        MENSAJES_DIA = mensajes
        RESUMEN = resumen
        total = sum(len(v) for v in mensajes.values())
        logging.info(f"Agenda cargada: {total} mensajes en {len(mensajes)} dias.")
        return True, None
    except Exception as e:
        logging.error(f"Error cargando agenda: {e}")
        return False, str(e)


async def agregar_a_rutina(dia: str, hora: int, minuto: int, mensaje: str) -> str:
    dia = dia.lower()
    if dia not in DIAS_VALIDOS:
        return f"Dia invalido: {dia}. Usa lunes a domingo."
    get_worksheet("Agenda").append_row([dia, hora, minuto, mensaje])
    cargar_agenda()
    return f"Agregado a la rutina: {dia} {hora:02d}:{minuto:02d} - {mensaje}"


async def quitar_de_rutina(dia: str, hora: int, minuto: int) -> str:
    dia = dia.lower()
    ws = get_worksheet("Agenda")
    rows = ws.get_all_values()
    fila = next(
        (i + 2 for i, r in enumerate(rows[1:])
         if r[0].lower() == dia and str(r[1]) == str(hora) and str(r[2]) == str(minuto)),
        None
    )
    if fila is None:
        return f"No se encontro recordatorio el {dia} a las {hora:02d}:{minuto:02d}."
    ws.delete_rows(fila)
    cargar_agenda()
    return f"Recordatorio eliminado: {dia} {hora:02d}:{minuto:02d}"


async def ver_rutina_diaria() -> str:
    if not MENSAJES_DIA:
        return "La agenda esta vacia."
    lineas = ["Agenda semanal:"]
    for dia in DIAS_VALIDOS:
        if dia not in MENSAJES_DIA:
            continue
        lineas.append(f"{dia.upper()}:")
        for h, m, msg in sorted(MENSAJES_DIA[dia]):
            lineas.append(f"  {h:02d}:{m:02d} — {msg}")
    return "\n".join(lineas)
