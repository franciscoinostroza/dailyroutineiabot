TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "agregar_a_rutina",
            "description": "Agrega una actividad a la RUTINA SEMANAL (Google Sheets). Para cosas RECURRENTES cada semana: medicacion, ejercicio, lectura. NO usar para eventos puntuales con fecha (eso va a crear_evento_calendario).",
            "parameters": {
                "type": "object",
                "properties": {
                    "dia": {"type": "string", "enum": ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]},
                    "hora": {"type": "integer", "minimum": 0, "maximum": 23},
                    "minuto": {"type": "integer", "minimum": 0, "maximum": 59},
                    "mensaje": {"type": "string"},
                },
                "required": ["dia", "hora", "minuto", "mensaje"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quitar_de_rutina",
            "description": "Elimina una actividad de la rutina semanal (Google Sheets). Solo para la rutina, no para el calendario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dia": {"type": "string", "enum": ["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]},
                    "hora": {"type": "integer", "minimum": 0, "maximum": 23},
                    "minuto": {"type": "integer", "minimum": 0, "maximum": 59},
                },
                "required": ["dia", "hora", "minuto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_compra",
            "description": "Registra una compra con supermercado y billetera. El bot calcula automaticamente los descuentos disponibles hoy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "producto": {"type": "string"},
                    "cantidad": {"type": "number"},
                    "precio_unitario": {"type": "number"},
                    "supermercado": {"type": "string", "enum": ["Coto", "Carrefour", "Dia"]},
                    "billetera": {"type": "string", "enum": ["MercadoPago", "Brubank", "Uala", "PersonalPay", "Supervielle", "Banco Ciudad", "Banco del Sol", "Prex"]},
                },
                "required": ["producto", "cantidad", "precio_unitario", "supermercado", "billetera"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_pago",
            "description": "Agrega un pago recurrente o suscripcion al sistema de recordatorios",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "dia_vencimiento": {"type": "integer", "minimum": 1, "maximum": 31},
                    "monto": {"type": "number"},
                    "categoria": {"type": "string", "description": "Opcional"},
                },
                "required": ["nombre", "dia_vencimiento", "monto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_pago_pagado",
            "description": "Marca un pago como pagado en el mes actual para que no siga apareciendo en recordatorios",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_pagos",
            "description": "Muestra todos los pagos y suscripciones registrados y su estado",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_gastos",
            "description": "Muestra el resumen de gastos del mes actual con totales y ahorros",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_descuentos",
            "description": "Muestra los descuentos disponibles hoy en supermercados con billeteras",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_rutina_diaria",
            "description": "Muestra la rutina semanal de Francisco (Google Sheets). Actividades RECURRENTES. NO muestra eventos del calendario.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_evento_calendario",
            "description": "Crea un evento en Google Calendar. USALA cada vez que Francisco pida agendar, crear, anotar o programar un evento, reunion, cita o turno. Calcula la fecha real a partir de la fecha indicada en el mensaje del sistema (hoy). NO uses fechas inventadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha en formato YYYY-MM-DD. Calculala a partir del mensaje del sistema que dice la fecha de hoy."},
                    "hora_inicio": {"type": "string", "description": "Hora de inicio HH:MM (formato 24h)"},
                    "hora_fin": {"type": "string", "description": "Hora de fin HH:MM (formato 24h)"},
                    "titulo": {"type": "string", "description": "Titulo del evento"},
                },
                "required": ["fecha", "hora_inicio", "hora_fin", "titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_eventos_calendario",
            "description": "Lista los eventos del calendario de Francisco para un dia especifico",
            "parameters": {
                "type": "object",
                "properties": {
                    "fecha": {"type": "string", "description": "Fecha YYYY-MM-DD. 'hoy' o 'manana' tambien son validos."},
                },
                "required": ["fecha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_evento_calendario",
            "description": "Elimina un evento del calendario por su numero (1, 2, 3...) segun la ultima lista de eventos consultada",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer", "minimum": 1, "description": "Numero del evento a eliminar (1 = primero)"},
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "iniciar_trabajo_tool",
            "description": "Inicia una sesion de trabajo freelance. Usala cuando Francisco diga que empieza a trabajar en un proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proyecto": {"type": "string", "description": "Nombre del proyecto (ej: 'Web Cliente X')"},
                    "descripcion": {"type": "string", "description": "Opcional. Detalle de la tarea."},
                },
                "required": ["proyecto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminar_trabajo_tool",
            "description": "Termina la sesion de trabajo activa. Usala cuando Francisco diga que termino de trabajar, 'corte', 'termine', etc.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_horas_trabajadas",
            "description": "Muestra las horas trabajadas en el mes actual, por proyecto",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_recordatorio_puntual",
            "description": "Agrega un recordatorio puntual (tarea, pendiente, cosa para hacer). NO es para agenda diaria, es para cosas sueltas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string", "description": "El texto del recordatorio"},
                },
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_recordatorios_pendientes",
            "description": "Muestra los recordatorios puntuales pendientes",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_recordatorio_hecho",
            "description": "Marca un recordatorio puntual como hecho por su numero (1, 2, 3...)",
            "parameters": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer", "minimum": 1, "description": "Numero del recordatorio (1 = primero)"},
                },
                "required": ["indice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_semanal_tool",
            "description": "Genera un resumen semanal con gastos, horas trabajadas, pagos proximos y eventos",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_presupuesto",
            "description": "Define un presupuesto mensual para una categoria de gastos (supermercado). Usala cuando Francisco diga 'presupuesto para X de $Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "description": "Categoria (ej: Coto, Carrefour)"},
                    "monto": {"type": "number", "description": "Monto mensual en pesos"},
                },
                "required": ["categoria", "monto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_presupuesto",
            "description": "Muestra el estado actual de los presupuestos mensuales con barras de progreso",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generar_estadisticas",
            "description": "Genera graficos de gastos y horas trabajadas. Usala cuando Francisco pida 'estadisticas', 'graficos' o 'como vengo con los gastos'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meses": {"type": "integer", "description": "Cantidad de meses a mostrar (default 3)"},
                },
                "required": [],
            },
        },
    },
]


async def execute_tool(nombre: str, args: dict) -> str:
    from . import rutina, compras, pagos, calendario, trabajo, recordatorios, resumen, presupuestos

    tool_map = {
        "agregar_a_rutina": rutina.agregar_a_rutina,
        "quitar_de_rutina": rutina.quitar_de_rutina,
        "ver_rutina_diaria": rutina.ver_rutina_diaria,
        "registrar_compra": compras.registrar_compra,
        "ver_gastos": compras.ver_gastos,
        "ver_descuentos": compras.ver_descuentos,
        "agregar_pago": pagos.agregar_pago,
        "marcar_pago_pagado": pagos.marcar_pago_pagado,
        "ver_pagos": pagos.ver_pagos,
        "crear_evento_calendario": calendario.crear_evento_calendario,
        "ver_eventos_calendario": calendario.ver_eventos_calendario,
        "eliminar_evento_calendario": calendario.eliminar_evento_calendario,
        "iniciar_trabajo_tool": trabajo.iniciar_trabajo_tool,
        "terminar_trabajo_tool": trabajo.terminar_trabajo_tool,
        "ver_horas_trabajadas": trabajo.ver_horas_trabajadas,
        "agregar_recordatorio_puntual": recordatorios.agregar_recordatorio_puntual,
        "ver_recordatorios_pendientes": recordatorios.ver_recordatorios_pendientes,
        "marcar_recordatorio_hecho": recordatorios.marcar_recordatorio_hecho,
        "resumen_semanal_tool": resumen.resumen_semanal_tool,
        "agregar_presupuesto": presupuestos.agregar_presupuesto,
        "ver_presupuesto": presupuestos.ver_presupuesto,
    }

    fn = tool_map.get(nombre)
    if fn is None:
        return f"Herramienta desconocida: {nombre}"
    return await fn(**args)
