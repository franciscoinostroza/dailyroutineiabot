import pytest
from bot.services.sheets import WorksheetPagos, WorksheetTrabajo, WorksheetRecordatorios


def test_worksheet_pagos_headers():
    assert "nombre" in WorksheetPagos.HEADERS
    assert "monto" in WorksheetPagos.HEADERS
    assert "dia_vencimiento" in WorksheetPagos.HEADERS
    assert "categoria" in WorksheetPagos.HEADERS
    assert "activo" in WorksheetPagos.HEADERS
    assert "ultimo_mes" in WorksheetPagos.HEADERS


def test_worksheet_trabajo_headers():
    assert "fecha" in WorksheetTrabajo.HEADERS
    assert "proyecto" in WorksheetTrabajo.HEADERS
    assert "hora_inicio" in WorksheetTrabajo.HEADERS
    assert "hora_fin" in WorksheetTrabajo.HEADERS
    assert "estado" in WorksheetTrabajo.HEADERS


def test_worksheet_recordatorios_headers():
    assert "texto" in WorksheetRecordatorios.HEADERS
    assert "fecha_creacion" in WorksheetRecordatorios.HEADERS
    assert "estado" in WorksheetRecordatorios.HEADERS
