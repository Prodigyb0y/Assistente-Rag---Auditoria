"""Embedder falso para testes offline: vetores determinísticos por 'saco de palavras' com hash.

Serve só para testar a lógica do pipeline (idempotência, ordenação, métrica). NÃO representa a
qualidade do modelo real de embeddings, e nenhum número obtido com ele vale como métrica do projeto.
"""
import re
import zlib

import numpy as np


class FakeEmbedder:
    def __init__(self, modelo: str = "fake-bow", dim: int = 256):
        self.modelo = modelo
        self.dim = dim
        self.chamadas = 0
        self.textos_embedados: list[str] = []

    def embed(self, textos, proposito="embedding"):
        self.chamadas += 1
        self.textos_embedados.extend(textos)
        m = np.zeros((len(textos), self.dim), dtype=np.float32)
        for i, t in enumerate(textos):
            for palavra in re.findall(r"\w+", t.lower()):
                m[i, zlib.crc32(palavra.encode()) % self.dim] += 1.0
        return m, sum(len(t.split()) for t in textos)
