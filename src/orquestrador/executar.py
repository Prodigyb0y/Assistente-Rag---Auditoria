"""Roda as primeiras N perguntas do gabarito pelo orquestrador (teste de fumaça do Bloco 5).

Uso (depois da ingestão, com as chaves no .env):
  python -m src.orquestrador.executar --limite 3

Mostra, por pergunta: status, rota, motivo de escalonamento, custo, tokens e latência. As decisões
ficam em logs/roteamento.jsonl. A avaliação completa (acerto, custo e latência nos 3 modos) é o Bloco 6.
"""
from __future__ import annotations

import argparse
import json
import sys

from ..agentes.anthropic_agente import AgenteAnthropic
from ..agentes.openai_agente import AgenteOpenAI
from ..agentes.prompts import carregar_prompt
from ..config import RAIZ, ConfigError, carregar_settings
from ..custo import ControleCusto, TabelaPrecos
from ..ingestao.embeddings import OpenAIEmbedder
from ..ingestao.indexador import carregar_indice
from ..recuperacao.buscador import Buscador
from .orquestrador import LogRoteamento, Orquestrador
from .politica import Politica, ordem_por_preco

PERGUNTAS = RAIZ / "dados" / "perguntas.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=3, help="roda só as N primeiras perguntas (padrão 3)")
    args = ap.parse_args(argv)
    try:
        s = carregar_settings()
    except ConfigError as e:
        print(f"ERRO de configuração: {e}")
        return 2
    tabela = TabelaPrecos.de_json(s.precos_path)
    controle = ControleCusto(tabela, s.orcamentos(), s.log_dir / "chamadas.jsonl")
    buscador = Buscador(carregar_indice(RAIZ / "indice"), OpenAIEmbedder(s, controle))
    prompt = carregar_prompt()
    agentes = {
        "openai": AgenteOpenAI(s, controle, buscador, tabela, prompt),
        "anthropic": AgenteAnthropic(s, controle, buscador, tabela, prompt),
    }
    ordem = ordem_por_preco(tabela, {"openai": s.openai_model, "anthropic": s.anthropic_model})
    pol = Politica.de_settings(s)
    orq = Orquestrador(agentes, ordem, pol, LogRoteamento(s.log_dir / "roteamento.jsonl"))
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))[: args.limite]

    print(f"prompt={prompt.versao} | ordem={' > '.join(ordem)} (preço de lista, tabela de {tabela.data_consulta}) | "
          f"confiança mínima={pol.confianca_minima} | tentativas={pol.max_tentativas}")
    for q in perguntas:
        r = orq.responder(q["pergunta"], q["id"])
        print(f"{q['id']} {r.status} rota={'>'.join(r.rota) or '-'} motivo={r.motivo_escalonamento or '-'} "
              f"tentativas={len(r.tentativas)} tokens={r.tokens_in}/{r.tokens_out} "
              f"custo={r.custo_total_usd:.6f} t={r.latencia_s:.1f}s")
    for p in ("openai", "anthropic"):
        print(f"gasto acumulado {p}: {controle.gasto(p):.6f} / teto {controle.orcamentos[p]:.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
