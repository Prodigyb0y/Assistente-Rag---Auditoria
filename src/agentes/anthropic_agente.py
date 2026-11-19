"""Agente de resposta da Anthropic (Messages API): tool use para a busca + saída estruturada.

Fluxo: chama o modelo com a ferramenta buscar_trechos e `output_config.format` (json_schema).
Enquanto stop_reason == "tool_use", executa a busca e devolve um bloco tool_result com o mesmo
tool_use_id; o conteúdo completo do assistente é reenviado (preserva blocos de raciocínio).
Não envia temperature/top_p/top_k (a API de 2026-10-21 os rejeita) e não força tool_choice.
"""
from __future__ import annotations

import time
from typing import Any

from ..config import Settings
from ..custo import ControleCusto, OrcamentoExcedido, TabelaPrecos
from ..recuperacao.buscador import Buscador
from .contrato import (DESCRICAO_FERRAMENTA, MAX_PASSOS_FERRAMENTA, NOME_FERRAMENTA, SCHEMA_BUSCA,
                       SCHEMA_RESPOSTA, ResultadoAgente, interpretar_saida)
from .ferramentas import FerramentaBusca
from .prompts import Prompt

PROVEDOR = "anthropic"


class AgenteAnthropic:
    provedor = PROVEDOR

    def __init__(self, settings: Settings, controle: ControleCusto, buscador: Buscador, tabela: TabelaPrecos,
                 prompt: Prompt, *, client: Any = None):
        self.settings = settings
        self.controle = controle
        self.buscador = buscador
        self.tabela = tabela
        self.prompt = prompt
        self.modelo = settings.anthropic_model
        self._client = client

    def _cliente(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.settings.chave("anthropic"), timeout=self.settings.timeout_s,
                                     max_retries=0)
        return self._client

    def _base(self) -> dict[str, Any]:
        return {
            "model": self.modelo,
            "max_tokens": self.settings.agent_max_output_tokens,
            "system": self.prompt.texto,
            "tools": [{"name": NOME_FERRAMENTA, "description": DESCRICAO_FERRAMENTA, "input_schema": SCHEMA_BUSCA}],
            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA_RESPOSTA}},
        }

    def responder(self, pergunta: str, pergunta_id: str = "") -> ResultadoAgente:
        r = ResultadoAgente(provedor=PROVEDOR, modelo=self.modelo, prompt_versao=self.prompt.versao,
                            prompt_sha=self.prompt.sha, pergunta_id=pergunta_id, pergunta=pergunta)
        ferramenta = FerramentaBusca(self.buscador, self.tabela)
        t_ini = time.perf_counter()
        texto_final = ""
        try:
            mensagens: list[dict[str, Any]] = [{"role": "user", "content": pergunta}]
            ctx_chars = len(self.prompt.texto) + len(pergunta)
            for passo in range(MAX_PASSOS_FERRAMENTA + 1):
                self.controle.reservar(PROVEDOR, self.modelo, ctx_chars, self.settings.agent_max_output_tokens,
                                       "agente")
                t0 = time.perf_counter()
                try:
                    msg = self._cliente().messages.create(**self._base(), messages=mensagens)
                except Exception as exc:
                    self.controle.registrar_erro(PROVEDOR, self.modelo, exc, time.perf_counter() - t0, "agente")
                    raise
                lat = time.perf_counter() - t0
                tin, tout = int(msg.usage.input_tokens), int(msg.usage.output_tokens)
                r.custo_llm_usd += self.controle.registrar(
                    PROVEDOR, self.modelo, tin, tout, lat, "agente",
                    pergunta_id=pergunta_id, passo=passo, prompt_versao=self.prompt.versao)
                r.tokens_in += tin
                r.tokens_out += tout
                r.n_chamadas_llm += 1

                if msg.stop_reason == "end_turn":
                    texto_final = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
                    break
                if msg.stop_reason != "tool_use":
                    r.erro = f"parada inesperada: stop_reason={msg.stop_reason}"
                    break
                if passo == MAX_PASSOS_FERRAMENTA:
                    r.erro = "limite de rodadas de ferramenta excedido"
                    break
                resultados = []
                for bloco in msg.content:
                    if getattr(bloco, "type", None) != "tool_use":
                        continue
                    entrada = bloco.input if isinstance(bloco.input, dict) else {}
                    resultado = ferramenta.executar(entrada.get("consulta"))
                    ctx_chars += len(resultado) + len(str(bloco.input))
                    resultados.append({"type": "tool_result", "tool_use_id": bloco.id, "content": resultado})
                mensagens.append({"role": "assistant", "content": msg.content})
                mensagens.append({"role": "user", "content": resultados})
        except OrcamentoExcedido:
            raise
        except Exception as exc:
            r.erro = f"{type(exc).__name__}: {exc}"
            r.excecao = exc

        r.saida_bruta = texto_final
        if r.erro is None:
            interp = interpretar_saida(texto_final, ferramenta.recuperados)
            r.resposta, r.schema_ok, r.citacoes_ok, r.erro = (
                interp.resposta, interp.schema_ok, interp.citacoes_ok, interp.erro)
        r.buscas = ferramenta.consultas
        r.trechos_recuperados = ferramenta.ordem_recuperados
        r.tokens_embedding = ferramenta.tokens_embedding
        r.custo_busca_usd = ferramenta.custo_usd
        r.latencia_s = time.perf_counter() - t_ini
        return r
