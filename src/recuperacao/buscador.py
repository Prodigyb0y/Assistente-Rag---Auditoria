"""Recuperação top-k por similaridade de cosseno sobre o índice em disco.

Os vetores do índice já são normalizados; o vetor da consulta também é normalizado aqui, então
o produto escalar é o cosseno. Empates são resolvidos pela ordem do índice (ordenação estável).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..ingestao.embeddings import Embedder
from ..ingestao.indexador import Indice


@dataclass(frozen=True)
class Resultado:
    posicao: int  # 1 = mais similar
    chunk_id: str
    doc_id: str
    secao_id: str
    titulo: str
    texto: str
    score: float


class Buscador:
    def __init__(self, indice: Indice, embedder: Embedder):
        if indice.modelo != embedder.modelo:
            raise ValueError(f"Índice feito com '{indice.modelo}', consulta com '{embedder.modelo}'")
        self.indice = indice
        self.embedder = embedder
        self.tokens_consulta = 0  # tokens gastos em embeddings de consulta, acumulado

    def buscar_lote(self, perguntas: list[str], k: int = 3) -> list[list[Resultado]]:
        if k < 1:
            raise ValueError("k deve ser >= 1")
        vetores, tokens = self.embedder.embed(perguntas, "consulta")
        self.tokens_consulta += tokens
        normas = np.linalg.norm(vetores, axis=1, keepdims=True)
        normas[normas == 0] = 1.0
        scores = (vetores / normas) @ self.indice.matriz.T  # (n_perguntas, n_trechos)
        k = min(k, scores.shape[1])
        saida: list[list[Resultado]] = []
        for linha in scores:
            ordem = np.argsort(-linha, kind="stable")[:k]
            saida.append([
                Resultado(posicao=p + 1, score=float(linha[i]),
                          **{c: self.indice.chunks[i][c]
                             for c in ("chunk_id", "doc_id", "secao_id", "titulo", "texto")})
                for p, i in enumerate(ordem)
            ])
        return saida

    def buscar(self, pergunta: str, k: int = 3) -> list[Resultado]:
        return self.buscar_lote([pergunta], k)[0]
