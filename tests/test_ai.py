import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from bot.services.ai import AIAssistant, _build_system_prompt


def test_system_prompt_contains_key_info():
    prompt = _build_system_prompt()
    assert "Francisco" in prompt
    assert "Argentina" in prompt
    assert "Workana" in prompt
    assert "Coto" in prompt
    assert "Carrefour" in prompt
    assert "Dia" in prompt


def test_ai_assistant_history_management():
    assistant = AIAssistant()
    assistant.append_user("123", "Hola")
    assistant.append_assistant("123", "Buenas")
    h = assistant.get_history("123")
    assert len(h) == 2
    assert h[0]["role"] == "user"
    assert h[1]["role"] == "assistant"


def test_ai_assistant_max_history():
    assistant = AIAssistant()
    for i in range(20):
        assistant.append_user("123", f"msg{i}")
    h = assistant.get_history("123")
    assert len(h) <= 12  # max_conversation_history = 12


@patch("bot.services.ai.openai_client.chat.completions.create")
async def test_process_message_text_response(mock_create):
    mock_choice = MagicMock()
    mock_choice.message.content = "Hola Francisco!"
    mock_choice.message.tool_calls = None
    mock_create.return_value = MagicMock(choices=[mock_choice])

    assistant = AIAssistant()
    result = await assistant.process_message("Hola", "123")
    assert "Hola" in result or result == "Hola Francisco!"


def test_telegram_button_map():
    from bot.services.ai import TELEGRAM_BUTTON_MAP
    assert TELEGRAM_BUTTON_MAP["📅 Rutina"] == "ver_rutina_diaria"
    assert TELEGRAM_BUTTON_MAP["💳 Pagos"] == "ver_pagos"
    assert TELEGRAM_BUTTON_MAP["🛒 Gastos"] == "ver_gastos"
    assert TELEGRAM_BUTTON_MAP["⏱ Trabajo"] == "ver_horas_trabajadas"
    assert TELEGRAM_BUTTON_MAP["📋 Tareas"] == "ver_recordatorios_pendientes"
    assert TELEGRAM_BUTTON_MAP["📊 Resumen"] == "resumen_semanal_tool"
