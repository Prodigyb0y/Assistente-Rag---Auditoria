"""Tela Gradio da demo. Fina de propósito: toda a regra está em servico.py (testado)."""
from __future__ import annotations

import json

import gradio as gr

from ..config import RAIZ
from .config_demo import ConfigDemo
from .formatar import AVISO, formatar
from .limites import extrair_ip, id_visitante
from .servico import ServicoDemo


def _exemplos(n: int = 3) -> list[list[str]]:
    perguntas = json.loads((RAIZ / "dados" / "perguntas.json").read_text(encoding="utf-8"))
    return [[q["pergunta"]] for q in (perguntas[0], perguntas[5], perguntas[12], perguntas[22])[:n + 1]]


def construir_demo(servico: ServicoDemo, cfg: ConfigDemo) -> gr.Blocks:
    sal = cfg.sal.get_secret_value()

    def responder(pergunta: str, request: gr.Request):
        host = request.client.host if request is not None and request.client else None
        cab = dict(request.headers) if request is not None and request.headers else {}
        visitante = id_visitante(extrair_ip(cab, host), sal)
        return formatar(servico.perguntar(pergunta, visitante))

    with gr.Blocks(title="Busca em políticas de auditoria (demo)") as demo:
        gr.Markdown("# Busca em políticas de auditoria — demo\n"
                    "Assistente que responde com base nos documentos fictícios da Gutenberg Systems e **cita a fonte**.")
        gr.Markdown(AVISO)
        entrada = gr.Textbox(label="Pergunta", lines=2, max_length=cfg.max_chars,
                             placeholder="Ex.: Com que frequência os acessos privilegiados devem ser revisados?")
        botao = gr.Button("Perguntar", variant="primary")
        gr.Examples(examples=_exemplos(), inputs=entrada)
        saida = gr.Markdown()
        detalhes = gr.Markdown()
        botao.click(responder, inputs=entrada, outputs=[saida, detalhes], concurrency_limit=4)
        entrada.submit(responder, inputs=entrada, outputs=[saida, detalhes], concurrency_limit=4)
        gr.Markdown(f"Limites desta demo: {cfg.por_visitante_dia} perguntas por visitante por dia; respostas repetidas "
                    "vêm do cache e não contam. Modelos: OpenAI e Anthropic (o mais barato responde primeiro).")
    return demo
