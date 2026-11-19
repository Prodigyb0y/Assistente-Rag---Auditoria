"""Chamadas mínimas a OpenAI e Anthropic, sempre passando pelo controle de custo.

Os SDKs são importados só quando necessário, e o cliente pode ser injetado (testes).
`max_retries=0` nos clientes: retries serão feitos de forma explícita e logada no orquestrador
(Bloco 5), para que nenhuma cobrança fique escondida em retentativas silenciosas do SDK.

Parâmetros de amostragem (temperature/top_p/top_k) NÃO são enviados: a API da Anthropic de
2026-10-21 os rejeita com HTTP 400 (migration-2026-10-21 na documentação oficial).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .custo import ControleCusto


@dataclass(frozen=True)
class Resposta:
    provedor: str
    modelo: str
    texto: str
    tokens_in: int
    tokens_out: int
    custo_usd: float
    latencia_s: float


def chamar_openai(prompt: str, settings: Settings, controle: ControleCusto, *, client: Any = None,
                  proposito: str = "teste") -> Resposta:
    modelo = settings.openai_model
    controle.reservar("openai", modelo, len(prompt), settings.max_output_tokens, proposito)
    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=settings.chave("openai"), timeout=settings.timeout_s, max_retries=0)
    t0 = time.perf_counter()
    try:
        resp = client.responses.create(model=modelo, input=prompt, max_output_tokens=settings.max_output_tokens)
    except Exception as exc:
        controle.registrar_erro("openai", modelo, exc, time.perf_counter() - t0, proposito)
        raise
    lat = time.perf_counter() - t0
    tin, tout = int(resp.usage.input_tokens), int(resp.usage.output_tokens)
    custo = controle.registrar("openai", modelo, tin, tout, lat, proposito)
    return Resposta("openai", modelo, resp.output_text, tin, tout, custo, lat)


def chamar_anthropic(prompt: str, settings: Settings, controle: ControleCusto, *, client: Any = None,
                     proposito: str = "teste") -> Resposta:
    modelo = settings.anthropic_model
    controle.reservar("anthropic", modelo, len(prompt), settings.max_output_tokens, proposito)
    if client is None:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.chave("anthropic"), timeout=settings.timeout_s, max_retries=0)
    t0 = time.perf_counter()
    try:
        msg = client.messages.create(
            model=modelo,
            max_tokens=settings.max_output_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        controle.registrar_erro("anthropic", modelo, exc, time.perf_counter() - t0, proposito)
        raise
    lat = time.perf_counter() - t0
    tin, tout = int(msg.usage.input_tokens), int(msg.usage.output_tokens)
    texto = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    custo = controle.registrar("anthropic", modelo, tin, tout, lat, proposito)
    return Resposta("anthropic", modelo, texto, tin, tout, custo, lat)
