"""Embeddings com o modelo da OpenAI, sempre passando pelo controle de custo.

Contrato (Embedder): atributo `modelo` e método `embed(textos, proposito) -> (matriz float32, tokens)`.
Formato da API conferido na referência oficial: embeddings.create(model, input, encoding_format);
resposta com data[i].embedding / data[i].index e usage.prompt_tokens.
"""
from __future__ import annotations

import time
from typing import Any, Protocol

import numpy as np

from ..config import Settings
from ..custo import ControleCusto


class Embedder(Protocol):
    modelo: str

    def embed(self, textos: list[str], proposito: str = "embedding") -> tuple[np.ndarray, int]: ...


class OpenAIEmbedder:
    def __init__(self, settings: Settings, controle: ControleCusto, *, client: Any = None, lote: int = 64):
        self.settings = settings
        self.controle = controle
        self.modelo = settings.embedding_model
        self.lote = lote
        self._client = client

    def _cliente(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.settings.chave("openai"),
                                  timeout=self.settings.timeout_s, max_retries=0)
        return self._client

    def embed(self, textos: list[str], proposito: str = "embedding") -> tuple[np.ndarray, int]:
        if not textos:
            return np.zeros((0, 0), dtype=np.float32), 0
        partes: list[np.ndarray] = []
        total_tokens = 0
        for i in range(0, len(textos), self.lote):
            lote = textos[i:i + self.lote]
            self.controle.reservar("openai", self.modelo, sum(len(t) for t in lote), 0, proposito)
            t0 = time.perf_counter()
            try:
                resp = self._cliente().embeddings.create(model=self.modelo, input=lote, encoding_format="float")
            except Exception as exc:
                self.controle.registrar_erro("openai", self.modelo, exc, time.perf_counter() - t0, proposito)
                raise
            lat = time.perf_counter() - t0
            dados = sorted(resp.data, key=lambda d: d.index)
            if len(dados) != len(lote):
                raise RuntimeError(f"API devolveu {len(dados)} embeddings para {len(lote)} textos")
            tokens = int(resp.usage.prompt_tokens)
            self.controle.registrar("openai", self.modelo, tokens, 0, lat, proposito, n_textos=len(lote))
            total_tokens += tokens
            partes.append(np.asarray([d.embedding for d in dados], dtype=np.float32))
        return np.vstack(partes), total_tokens
