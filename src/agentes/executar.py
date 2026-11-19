"""Roda as perguntas do gabarito em cada agente e grava as respostas em docs/resultados/.

Uso (depois da ingestão):
  python -m src.agentes.executar --provedor openai --limite 3     # teste barato com 3 perguntas
  python -m src.agentes.executar --provedor ambos                 # as 30 perguntas nos dois agentes

Critério do Bloco 4: "saída válida" = JSON conforme o schema E todas as citações entre os trechos
que o agente de fato recuperou. Não mede acerto da resposta (isso é o Bloco 6).
Se o teto de gasto for atingido, a execução para e o que já foi gravado fica salvo.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from ..config import RAIZ, ConfigError, carregar_settings
from ..custo import ControleCusto, OrcamentoExcedido, TabelaPrecos
from ..ingestao.embeddings import OpenAIEmbedder
from ..ingestao.indexador import carregar_indice
from ..recuperacao.buscador import Buscador
from .anthropic_agente import AgenteAnthropic
from .contrato import ResultadoAgente
from .openai_agente import AgenteOpenAI
from .prompts import carregar_prompt

PERGUNTAS = RAIZ / "dados" / "perguntas.json"
DIR_SAIDA = RAIZ / "docs" / "resultados"


def _resumo(resultados: list[ResultadoAgente]) -> dict:
    n = len(resultados)
    return {
        "perguntas_executadas": n,
        "saidas_validas": sum(r.valido for r in resultados),
        "saidas_invalidas": sum(not r.valido for r in resultados),
        "tokens_in": sum(r.tokens_in for r in resultados),
        "tokens_out": sum(r.tokens_out for r in resultados),
        "custo_total_usd": sum(r.custo_total_usd for r in resultados),
        "latencia_media_s": (sum(r.latencia_s for r in resultados) / n) if n else 0.0,
    }


def _gravar(provedor: str, modelo: str, prompt, resultados: list[ResultadoAgente], limite: int | None) -> None:
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    corpo = {
        "data": time.strftime("%Y-%m-%d"), "provedor": provedor, "modelo": modelo,
        "prompt_versao": prompt.versao, "prompt_sha": prompt.sha, "limite_de_perguntas": limite,
        "resumo": _resumo(resultados), "resultados": [r.para_dict() for r in resultados],
    }
    (DIR_SAIDA / f"agentes_{provedor}.json").write_text(
        json.dumps(corpo, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedor", choices=["openai", "anthropic", "ambos"], default="ambos")
    ap.add_argument("--limite", type=int, default=None, help="roda só as N primeiras perguntas")
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
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    if args.limite:
        perguntas = perguntas[: args.limite]

    agentes = []
    if args.provedor in ("openai", "ambos"):
        agentes.append(AgenteOpenAI(s, controle, buscador, tabela, prompt))
    if args.provedor in ("anthropic", "ambos"):
        agentes.append(AgenteAnthropic(s, controle, buscador, tabela, prompt))

    print(f"prompt={prompt.versao} (sha {prompt.sha}) | perguntas={len(perguntas)}")
    codigo = 0
    for ag in agentes:
        resultados: list[ResultadoAgente] = []
        try:
            for q in perguntas:
                r = ag.responder(q["pergunta"], q["id"])
                resultados.append(r)
                marca = "ok " if r.valido else "INV"
                print(f"[{ag.provedor}] {q['id']} {marca} tokens={r.tokens_in}/{r.tokens_out} "
                      f"custo={r.custo_total_usd:.6f} t={r.latencia_s:.1f}s" + (f" erro={r.erro}" if r.erro else ""))
                _gravar(ag.provedor, ag.modelo, prompt, resultados, args.limite)
        except OrcamentoExcedido as e:
            print(f"[{ag.provedor}] PARADO pelo teto de gasto: {e}")
            codigo = 1
        resumo = _resumo(resultados)
        print(f"== {ag.provedor}: {resumo['saidas_validas']}/{resumo['perguntas_executadas']} saídas válidas | "
              f"tokens {resumo['tokens_in']}/{resumo['tokens_out']} | custo US$ {resumo['custo_total_usd']:.6f} | "
              f"latência média {resumo['latencia_media_s']:.1f}s")
        if resumo["saidas_invalidas"]:
            codigo = max(codigo, 1)
    for p in ("openai", "anthropic"):
        print(f"gasto acumulado {p}: {controle.gasto(p):.6f} / teto {controle.orcamentos[p]:.2f} USD")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
