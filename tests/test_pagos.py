import pytest
from unittest.mock import patch, MagicMock

from bot.services.sheets import WorksheetPagos
from bot.tools.pagos import agregar_pago, marcar_pago_pagado, ver_pagos


@patch("bot.tools.pagos.WorksheetPagos.append")
def test_agregar_pago(mock_append):
    result = agregar_pago("Netflix", 15, 3200, "streaming")
    assert "Netflix" in result
    assert "$3,200" in result
    assert "vence el dia 15" in result


@patch("bot.tools.pagos.WorksheetPagos.append")
def test_agregar_pago_dia_invalido(mock_append):
    result = agregar_pago("Netflix", 32, 3200)
    assert "Dia de vencimiento invalido" in result
    mock_append.assert_not_called()


@patch("bot.tools.pagos.WorksheetPagos.find_row")
@patch("bot.tools.pagos.WorksheetPagos.mark_paid")
def test_marcar_pago_pagado_not_found(mock_mark, mock_find):
    mock_find.return_value = None
    result = marcar_pago_pagado("Inexistente")
    assert "No se encontro" in result
    mock_mark.assert_not_called()


@patch("bot.tools.pagos.WorksheetPagos.read_all")
def test_ver_pagos_empty(mock_read):
    mock_read.return_value = []
    result = ver_pagos()
    assert "No hay pagos registrados" in result


@patch("bot.tools.pagos.WorksheetPagos.read_all")
def test_ver_pagos_with_data(mock_read):
    mock_read.return_value = [
        {"nombre": "Netflix", "monto": "3200", "dia_vencimiento": "15", "activo": "si", "ultimo_mes": ""},
        {"nombre": "Renta", "monto": "50000", "dia_vencimiento": "5", "activo": "no", "ultimo_mes": "2026-05"},
    ]
    result = ver_pagos()
    assert "Netflix" in result
    assert "Renta" in result
    assert "$3,200" in result
    assert "$50,000" in result
