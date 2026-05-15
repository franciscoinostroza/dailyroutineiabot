import pytest
from unittest.mock import patch, MagicMock

from bot.tools.recordatorios import (
    agregar_recordatorio_puntual,
    ver_recordatorios_pendientes,
    marcar_recordatorio_hecho,
)


@patch("bot.tools.recordatorios.WorksheetRecordatorios.append")
def test_agregar_recordatorio(mock_append):
    result = agregar_recordatorio_puntual("Llamar al medico")
    assert "Llamar al medico" in result
    assert "Recordatorio agregado" in result


@patch("bot.tools.recordatorios.WorksheetRecordatorios.read_pending")
def test_ver_recordatorios_empty(mock_read):
    mock_read.return_value = []
    result = ver_recordatorios_pendientes()
    assert "No hay recordatorios" in result


@patch("bot.tools.recordatorios.WorksheetRecordatorios.read_pending")
def test_ver_recordatorios_with_data(mock_read):
    mock_read.return_value = [
        {"texto": "Comprar pan", "fecha_creacion": "2026-05-15", "estado": "pendiente"},
        {"texto": "Llamar banco", "fecha_creacion": "2026-05-14", "estado": "pendiente"},
    ]
    result = ver_recordatorios_pendientes()
    assert "Comprar pan" in result
    assert "Llamar banco" in result
    assert "1." in result
    assert "2." in result


@patch("bot.tools.recordatorios.WorksheetRecordatorios.read_pending")
@patch("bot.tools.recordatorios.WorksheetRecordatorios.find_row_by_text")
@patch("bot.tools.recordatorios.WorksheetRecordatorios.mark_done")
def test_marcar_recordatorio_hecho(mock_mark, mock_find, mock_read):
    mock_read.return_value = [
        {"texto": "Comprar pan", "fecha_creacion": "2026-05-15", "estado": "pendiente"},
    ]
    mock_find.return_value = 5
    result = marcar_recordatorio_hecho(1)
    assert "Comprar pan" in result
    assert "marcado como hecho" in result
    mock_mark.assert_called_once_with(5)


@patch("bot.tools.recordatorios.WorksheetRecordatorios.read_pending")
def test_marcar_recordatorio_indice_invalido(mock_read):
    mock_read.return_value = [
        {"texto": "Comprar pan", "fecha_creacion": "2026-05-15", "estado": "pendiente"},
    ]
    result = marcar_recordatorio_hecho(5)
    assert "Numero invalido" in result
