from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RoutineEntry:
    dia: str
    hora: int
    minuto: int
    mensaje: str


@dataclass
class Purchase:
    fecha: str
    producto: str
    cantidad: float
    precio_unitario: float
    precio_total: float
    supermercado: str
    billetera: str
    descuento_pct: float
    ahorro: float
    precio_final: float


@dataclass
class Discount:
    supermercado: str
    billetera: str
    porcentaje: float
    dia: str
    tope: Optional[float] = None
    notas: str = ""


@dataclass
class Payment:
    nombre: str
    monto: float
    dia_vencimiento: int
    categoria: str = ""
    activo: bool = True
    ultimo_mes: str = ""


@dataclass
class WorkSession:
    fecha: str
    proyecto: str
    hora_inicio: str
    hora_fin: str
    descripcion: str
    estado: str
    minutos: float = 0.0


@dataclass
class Reminder:
    texto: str
    fecha_creacion: str
    estado: str = "pendiente"


@dataclass
class CalendarEvent:
    id: str
    titulo: str
    fecha: str
    hora: str
