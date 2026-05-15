from .registry import TOOLS, execute_tool
from .rutina import agregar_a_rutina, quitar_de_rutina, ver_rutina_diaria
from .compras import registrar_compra, ver_gastos, ver_descuentos
from .pagos import agregar_pago, marcar_pago_pagado, ver_pagos
from .calendario import crear_evento_calendario, ver_eventos_calendario, eliminar_evento_calendario
from .trabajo import iniciar_trabajo_tool, terminar_trabajo_tool, ver_horas_trabajadas
from .recordatorios import agregar_recordatorio_puntual, ver_recordatorios_pendientes, marcar_recordatorio_hecho
from .resumen import resumen_semanal_tool
from .presupuestos import agregar_presupuesto, ver_presupuesto
from .estadisticas import generar_grafico_gastos, generar_grafico_trabajo
from .exportar import exportar_gastos, exportar_pagos, exportar_trabajo
from .proyectos import (
    add_new_project, generate_documentation, view_project_info,
)
from .habitos import registrar_habito as ai_registrar_habito, ver_habitos as ai_ver_habitos
from .deadlines import agregar_deadline as ai_agregar_deadline, ver_deadlines as ai_ver_deadlines
from .facturas import agregar_factura as ai_agregar_factura, ver_facturas as ai_ver_facturas
