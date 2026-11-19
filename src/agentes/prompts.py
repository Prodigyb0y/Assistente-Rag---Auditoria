"""Prompts versionados em arquivos (prompts/<nome>_<versao>.md).

O identificador da versão (ex.: agente_resposta_v1) e um hash curto do conteúdo são registrados
em cada resposta. Mudou o texto do prompt? Crie uma nova versão (v2) e reexecute a avaliação.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..config import RAIZ

DIR_PROMPTS = RAIZ / "prompts"


@dataclass(frozen=True)
class Prompt:
    versao: str  # ex.: "agente_resposta_v1"
    sha: str     # primeiros 12 caracteres do SHA-256 do conteúdo
    texto: str


def carregar_prompt(nome: str = "agente_resposta", versao: str = "v1", diretorio: Path = DIR_PROMPTS) -> Prompt:
    arq = Path(diretorio) / f"{nome}_{versao}.md"
    if not arq.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {arq}")
    texto = arq.read_text(encoding="utf-8").strip()
    return Prompt(versao=f"{nome}_{versao}", sha=hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12], texto=texto)
