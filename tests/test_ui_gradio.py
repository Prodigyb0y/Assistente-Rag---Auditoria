"""Monta a tela com o Gradio REAL (sem chamar API): pega parâmetros inválidos antes de abrir o app.

Pula sozinho onde o Gradio não está instalado.
"""
from __future__ import annotations

import pytest

gr = pytest.importorskip("gradio")

from pydantic import SecretStr  # noqa: E402

from src.interface.servico import RespostaDemo  # noqa: E402
from src.interface.ui import N_CHIPS, construir_demo, opcoes_launch  # noqa: E402


class _Cfg:
    sal = SecretStr("sal-de-teste")
    por_visitante_dia = 5
    max_chars = 300


class _Servico:
    def perguntar(self, texto, visitante):
        return RespostaDemo(status="ok", resposta="R", encontrado=True, confianca="alta",
                            citacoes=[{"documento": "POL-ACE", "secao": "ACE-3"}], provedor="x",
                            aceita_pela_regra=True, restantes_visitante=4)

    def restantes(self, visitante):
        return 5


def test_tela_monta_com_o_gradio_real():
    demo = construir_demo(_Servico(), _Cfg())
    assert isinstance(demo, gr.Blocks)
    tipos = [type(b).__name__ for b in demo.blocks.values()]
    assert "Chatbot" in tipos and "Radio" in tipos and tipos.count("Button") >= N_CHIPS + 2   # chips + Enviar + Nova conversa


def test_opcoes_de_launch_validas():
    op = opcoes_launch()
    assert set(op) == {"theme", "css"} and isinstance(op["css"], str)
