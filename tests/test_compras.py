import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from bot.config import settings
from bot.tools.compras import parsear_tope, es_ultimo_sabado


def test_parsear_tope_none():
    assert parsear_tope(None) is None
    assert parsear_tope("") is None
    assert parsear_tope("sin tope") is None
    assert parsear_tope("-") is None


def test_parsear_tope_value():
    assert parsear_tope("5000") == 5000.0
    assert parsear_tope("$5,000.00") == 500000.0  # strips non-digits
    assert parsear_tope("20000") == 20000.0


def test_es_ultimo_sabado_not_saturday():
    with patch("bot.tools.compras.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 15, 12, 0)  # Friday, weekday 4
        # weekday() returns 4 for Friday, so es_ultimo_sabado returns False
        assert es_ultimo_sabado() is False


@patch("bot.tools.compras.datetime")
def test_es_ultimo_sabado_true(mock_dt):
    # May 2026 has 31 days. Last Saturday would be May 30 (day 30, 30+7=37 > 31)
    mock_dt.now.return_value = datetime(2026, 5, 30, 12, 0)  # Saturday, weekday 5
    assert es_ultimo_sabado() is True


@patch("bot.tools.compras.datetime")
def test_es_ultimo_sabado_false(mock_dt):
    # May 2026, May 23 is a Saturday but not the last one (23+7=30 <= 31)
    mock_dt.now.return_value = datetime(2026, 5, 23, 12, 0)
    assert es_ultimo_sabado() is False
