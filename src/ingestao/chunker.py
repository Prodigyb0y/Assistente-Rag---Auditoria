"""Divisão dos documentos em trechos, um por seção, preservando o identificador da seção.

Decisão: as seções dos documentos fictícios são curtas (um parágrafo), então cada seção vira
exatamente um trecho. Isso mantém o gabarito (documento + id da seção) alinhado 1:1 com o índice.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_RE_DOC = re.compile(r"^#\s+(\S+)", re.M)
_RE_SEC = re.compile(r"^##\s+(\S+)\s+(.+?)\s*$", re.M)

# Limite de segurança: o modelo de embeddings aceita ~8k tokens; 8000 caracteres fica bem abaixo.
MAX_CHARS_TRECHO = 8000


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    secao_id: str
    titulo: str
    texto: str

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_id}/{self.secao_id}"

    @property
    def texto_embedding(self) -> str:
        """Texto que vai para o modelo de embeddings (inclui código, seção e título como contexto)."""
        return f"{self.doc_id} {self.secao_id} {self.titulo}\n{self.texto}"

    def hash(self, modelo: str) -> str:
        return hashlib.sha256(f"{modelo}\n{self.texto_embedding}".encode("utf-8")).hexdigest()


def dividir_documento(conteudo: str, origem: str = "") -> list[Chunk]:
    m = _RE_DOC.search(conteudo)
    if not m:
        raise ValueError(f"{origem}: título '# CODIGO — ...' não encontrado")
    doc_id = m.group(1)
    secoes = list(_RE_SEC.finditer(conteudo))
    if not secoes:
        raise ValueError(f"{origem}: nenhuma seção '## ID Título' encontrada")
    chunks: list[Chunk] = []
    for i, s in enumerate(secoes):
        fim = secoes[i + 1].start() if i + 1 < len(secoes) else len(conteudo)
        corpo = " ".join(conteudo[s.end():fim].split())
        if not corpo:
            raise ValueError(f"{origem}: seção {s.group(1)} vazia")
        if len(corpo) > MAX_CHARS_TRECHO:
            raise ValueError(f"{origem}: seção {s.group(1)} excede {MAX_CHARS_TRECHO} caracteres")
        chunks.append(Chunk(doc_id=doc_id, secao_id=s.group(1), titulo=s.group(2), texto=corpo))
    return chunks


def carregar_documentos(diretorio: Path) -> list[Chunk]:
    arquivos = sorted(Path(diretorio).glob("*.md"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum .md em {diretorio}")
    chunks: list[Chunk] = []
    for arq in arquivos:
        chunks.extend(dividir_documento(arq.read_text(encoding="utf-8"), arq.name))
    ids = [c.chunk_id for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("chunk_id duplicado entre documentos")
    return chunks
