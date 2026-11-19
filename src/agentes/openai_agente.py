"""Agente de resposta da OpenAI (Responses API): tool calling para a busca + saída estruturada.

Fluxo: chama o modelo com a ferramenta buscar_trechos e `text.format` (json_schema, strict).
Enquanto houver function_call, executa a busca e devolve um function_call_output, encadeando com
previous_response_id. A resposta final deve ser o JSON do contrato, validado em código.
Cada chamada passa pelo controle de custo (reserva antes, registro de tokens depois).
"""
from __future__ import annotations

import json
import time
from typing import Any

from ..config import Settings
from ..custo import ControleCusto, OrcamentoExcedido, TabelaPrecos
from ..recuperacao.buscador import Buscador
from .contrato import (DESCRICAO_FERRAMENTA, MAX_PASSOS_FERRAMENTA, NOME_FERRAMENTA, SCHEMA_BUSCA,
                       SCHEMA_RESPOSTA, ResultadoAgente, interpretar_saida)
from .ferramentas import FerramentaBusca
from .prompts import Prompt

PROVEDOR = "openai"


class AgenteOpenAI:
    provedor = PROVEDOR

    def __init__(self, settings: Settings, controle: ControleCusto, buscador: Buscador, tabela: TabelaPrecos,
                 prompt: Prompt, *, client: Any = None):
        self.settings = settings
        self.controle = controle
        self.buscador = buscador
        self.tabela = tabela
        self.prompt = prompt
        self.modelo = settings.openai_model
        self._client = client

    def _cliente(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.settings.chave("openai"), timeout=self.settings.timeout_s,
                                  max_retries=0)
        return self._client

    def _base(self) -> dict[str, Any]:
        return {
            "model": self.modelo,
            "instructions": self.prompt.texto,
            "tools": [{"type": "function", "name": NOME_FERRAMENTA, "description": DESCRICAO_FERRAMENTA,
                       "parameters": SCHEMA_BUSCA, "strict": True}],
            "text": {"format": {"type": "json_schema", "name": "resposta_auditoria",
                                "schema": SCHEMA_RESPOSTA, "strict": True}},
            "max_output_tokens": self.settings.agent_max_output_tokens,
        }

    def responder(self, pergunta: str, pergunta_id: str = "") -> ResultadoAgente:
        r = ResultadoAgente(provedor=PROVEDOR, modelo=self.modelo, prompt_versao=self.prompt.versao,
                            prompt_sha=self.prompt.sha, pergunta_id=pergunta_id, pergunta=pergunta)
        ferramenta = FerramentaBusca(self.buscador, self.tabela)
        t_ini = time.perf_counter()
        texto_final = ""
        try:
            entrada: list[dict[str, Any]] = [{"role": "user", "content": pergunta}]
            anterior: str | None = None
            ctx_chars = len(self.prompt.texto) + len(pergunta)
            for passo in range(MAX_PASSOS_FERRAMENTA + 1):
                self.controle.reservar(PROVEDOR, self.modelo, ctx_chars, self.settings.agent_max_output_tokens,
                                       "agente")
                pedido = dict(self._base(), input=entrada)
                if anterior:
                    pedido["previous_response_id"] = anterior
                t0 = time.perf_counter()
                try:
                    resp = self._cliente().responses.create(**pedido)
                except Exception as exc:
                    self.controle.registrar_erro(PROVEDOR, self.modelo, exc, time.perf_counter() - t0, "agente")
                    raise
                lat = time.perf_counter() - t0
                tin, tout = int(resp.usage.input_tokens), int(resp.usage.output_tokens)
                r.custo_llm_usd += self.controle.registrar(
                    PROVEDOR, self.modelo, tin, tout, lat, "agente",
                    pergunta_id=pergunta_id, passo=passo, prompt_versao=self.prompt.versao)
                r.tokens_in += tin
                r.tokens_out += tout
                r.n_chamadas_llm += 1

                if getattr(resp, "status", "completed") == "incomplete":
                    r.erro = "resposta incompleta (limite de tokens de saída)"
                    break
                chamadas = [it for it in resp.output if getattr(it, "type", None) == "function_call"]
                if not chamadas:
                    texto_final = resp.output_text or ""
                    break
                if passo == MAX_PASSOS_FERRAMENTA:
                    r.erro = "limite de rodadas de ferramenta excedido"
                    break
                saidas = []
                for c in chamadas:
                    try:
                        consulta = json.loads(c.arguments).get("consulta")
                    except (json.JSONDecodeError, AttributeError):
                        consulta = None
                    resultado = ferramenta.executar(consulta)
                    ctx_chars += len(resultado) + len(str(c.arguments))
                    saidas.append({"type": "function_call_output", "call_id": c.call_id, "output": resultado})
                entrada, anterior = saidas, resp.id
        except OrcamentoExcedido:
            raise
        except Exception as exc:
            r.erro = f"{type(exc).__name__}: {exc}"

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
