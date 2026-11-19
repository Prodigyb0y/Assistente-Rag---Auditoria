"""Índice em disco e ingestão idempotente.

Formato em disco (pasta `indice/`):
  chunks.json  -> modelo, dimensão e a lista de trechos (id, doc, seção, título, texto, hash)
  vetores.npy  -> matriz float32 (n_trechos x dim), normalizada, na mesma ordem de chunks.json

Idempotência: cada trecho tem um hash (modelo + texto embedado). Na reingestão, só os trechos
cujo hash ainda não está no índice vão para a API; rodar de novo sem mudanças faz 0 chamadas.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .chunker import Chunk
from .embeddings import Embedder


@dataclass
class Indice:
    modelo: str
    chunks: list[dict]
    matriz: np.ndarray

    @property
    def hash(self) -> str:
        return hashlib.sha256("\n".join(c["hash"] for c in self.chunks).encode()).hexdigest()


@dataclass(frozen=True)
class RelatorioIngestao:
    total: int
    novos: int
    reaproveitados: int
    removidos: int
    tokens: int


def _normalizar(m: np.ndarray) -> np.ndarray:
    normas = np.linalg.norm(m, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return (m / normas).astype(np.float32)


def carregar_indice(dir_indice: Path) -> Indice:
    d = Path(dir_indice)
    if not (d / "chunks.json").exists() or not (d / "vetores.npy").exists():
        raise FileNotFoundError(f"Índice não encontrado em {d}. Rode a ingestão primeiro.")
    meta = json.loads((d / "chunks.json").read_text(encoding="utf-8"))
    matriz = np.load(d / "vetores.npy")
    if matriz.shape[0] != len(meta["chunks"]):
        raise ValueError("Índice corrompido: número de vetores difere do número de trechos")
    return Indice(modelo=meta["modelo"], chunks=meta["chunks"], matriz=matriz)


def _escrever_atomico(destino: Path, escrever) -> None:
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    with tmp.open("wb") as f:
        escrever(f)
    os.replace(tmp, destino)


def ingerir(chunks: list[Chunk], dir_indice: Path, embedder: Embedder) -> RelatorioIngestao:
    if not chunks:
        raise ValueError("Nenhum trecho para ingerir")
    d = Path(dir_indice)
    d.mkdir(parents=True, exist_ok=True)
    modelo = embedder.modelo

    cache: dict[str, np.ndarray] = {}
    hashes_antigos: set[str] = set()
    try:
        antigo = carregar_indice(d)
        hashes_antigos = {c["hash"] for c in antigo.chunks}
        if antigo.modelo == modelo:  # outro modelo => vetores incompatíveis, nada é reaproveitado
            cache = {c["hash"]: antigo.matriz[i] for i, c in enumerate(antigo.chunks)}
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
        pass

    hashes = [c.hash(modelo) for c in chunks]
    pendentes: dict[str, Chunk] = {}
    for h, c in zip(hashes, chunks):
        if h not in cache and h not in pendentes:
            pendentes[h] = c

    tokens = 0
    if pendentes:
        novos_vetores, tokens = embedder.embed([c.texto_embedding for c in pendentes.values()], "ingestao")
        novos_vetores = _normalizar(np.asarray(novos_vetores, dtype=np.float32))
        for h, v in zip(pendentes.keys(), novos_vetores):
            cache[h] = v

    matriz = _normalizar(np.stack([cache[h] for h in hashes]))
    meta = {
        "modelo": modelo,
        "dim": int(matriz.shape[1]),
        "chunks": [
            {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "secao_id": c.secao_id, "titulo": c.titulo,
             "texto": c.texto, "hash": h}
            for c, h in zip(chunks, hashes)
        ],
    }
    # Ordem de escrita: vetores primeiro, depois metadados (o que o leitor valida).
    _escrever_atomico(d / "vetores.npy", lambda f: np.save(f, matriz))
    _escrever_atomico(d / "chunks.json",
                      lambda f: f.write(json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8")))

    novos = len(pendentes)
    return RelatorioIngestao(
        total=len(chunks), novos=novos, reaproveitados=len(set(hashes)) - novos,
        removidos=len(hashes_antigos - set(hashes)), tokens=tokens,
    )
