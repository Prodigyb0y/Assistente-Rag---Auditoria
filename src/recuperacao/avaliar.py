"""Roda a avaliação de recall@k nas 30 perguntas e grava o relatório em docs/resultados/.

Uso (depois da ingestão):  python -m src.recuperacao.avaliar
Gera docs/resultados/recall.json e docs/resultados/recall.md.
"""
from __future__ import annotations

import json
import sys

from ..config import RAIZ, ConfigError, carregar_settings
from ..custo import ControleCusto, TabelaPrecos
from ..ingestao.embeddings import OpenAIEmbedder
from ..ingestao.indexador import carregar_indice
from .avaliacao import avaliar, gerar_relatorio_md
from .buscador import Buscador

DIR_INDICE = RAIZ / "indice"
PERGUNTAS = RAIZ / "dados" / "perguntas.json"
DIR_SAIDA = RAIZ / "docs" / "resultados"


def main() -> int:
    try:
        s = carregar_settings()
    except ConfigError as e:
        print(f"ERRO de configuração: {e}")
        return 2
    tabela = TabelaPrecos.de_json(s.precos_path)
    controle = ControleCusto(tabela, s.orcamentos(), s.log_dir / "chamadas.jsonl")
    indice = carregar_indice(DIR_INDICE)
    buscador = Buscador(indice, OpenAIEmbedder(s, controle))
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    resultado = avaliar(perguntas, buscador, tabela)

    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    (DIR_SAIDA / "recall.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    (DIR_SAIDA / "recall.md").write_text(gerar_relatorio_md(resultado), encoding="utf-8")

    for k, v in resultado["recall"].items():
        print(f"recall@{k} = {v['acertos']}/{v['total']} = {v['recall']:.3f}")
    print(f"tokens_embedding_consultas={resultado['tokens_embedding_consultas']} "
          f"custo_usd={resultado['custo_consultas_usd']:.6f}")
    print(f"relatório: {DIR_SAIDA / 'recall.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
