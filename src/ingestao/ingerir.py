"""Ingestão: lê dados/documentos, gera embeddings só do que mudou e salva o índice em indice/.

Uso (na raiz do projeto, com .env preenchido):  python -m src.ingestao.ingerir
Rodar de novo sem alterar os documentos não faz nenhuma chamada à API.
"""
from __future__ import annotations

import sys

from ..config import RAIZ, ConfigError, carregar_settings
from ..custo import ControleCusto, TabelaPrecos
from .chunker import carregar_documentos
from .embeddings import OpenAIEmbedder
from .indexador import ingerir

DIR_DOCS = RAIZ / "dados" / "documentos"
DIR_INDICE = RAIZ / "indice"


def main() -> int:
    try:
        s = carregar_settings()
    except ConfigError as e:
        print(f"ERRO de configuração: {e}")
        return 2
    controle = ControleCusto(TabelaPrecos.de_json(s.precos_path), s.orcamentos(), s.log_dir / "chamadas.jsonl")
    chunks = carregar_documentos(DIR_DOCS)
    rel = ingerir(chunks, DIR_INDICE, OpenAIEmbedder(s, controle))
    print(f"trechos={rel.total} novos={rel.novos} reaproveitados={rel.reaproveitados} "
          f"removidos={rel.removidos} tokens_embedding={rel.tokens}")
    print(f"gasto acumulado openai: {controle.gasto('openai'):.6f} / teto {controle.orcamentos['openai']:.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
