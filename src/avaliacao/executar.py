"""Roda a avaliação completa e gera a tabela de resultados.

Uso (depois da ingestão, com as chaves no .env):
  python -m src.avaliacao.executar                     # os 3 modos x 30 perguntas (~US$ 0,10 no total)
  python -m src.avaliacao.executar --modos openai --limite 3   # teste barato
  python -m src.avaliacao.executar --so-relatorio      # refaz a tabela sem chamar API (ex.: após editar
                                                       #   dados/acerto_manual.json ou dados/fatos_chave.json)

Saídas: docs/resultados/avaliacao.json, docs/resultados/avaliacao.md (tabela gerada por script) e
docs/resultados/avaliacao_<modo>.json (parcial, gravado a cada pergunta).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from ..config import RAIZ, ConfigError, carregar_settings
from ..custo import ControleCusto, TabelaPrecos
from .acerto import carregar_fatos, carregar_manual
from .harness import MODOS, Linha, agregar, executar_modo, precos_dos_modos, recalcular
from .relatorio import gerar_markdown, para_json

PERGUNTAS = RAIZ / "dados" / "perguntas.json"
FATOS = RAIZ / "dados" / "fatos_chave.json"
MANUAL = RAIZ / "dados" / "acerto_manual.json"
SAIDA = RAIZ / "docs" / "resultados"


def _escrever(resumos, linhas, meta) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "avaliacao.json").write_text(
        json.dumps(para_json(resumos, linhas, meta), ensure_ascii=False, indent=1), encoding="utf-8")
    (SAIDA / "avaliacao.md").write_text(gerar_markdown(resumos, linhas, meta), encoding="utf-8")


def _so_relatorio() -> int:
    arq = SAIDA / "avaliacao.json"
    if not arq.exists():
        print("Nada para regenerar: rode a avaliação primeiro.")
        return 2
    salvo = json.loads(arq.read_text(encoding="utf-8"))
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    fatos, manual = carregar_fatos(FATOS), carregar_manual(MANUAL)
    linhas = {m: recalcular(ls, perguntas, fatos, manual) for m, ls in salvo["linhas"].items()}
    resumos = {m: agregar(m, ls, len(perguntas)) for m, ls in linhas.items()}
    _escrever(resumos, linhas, salvo["meta"])
    print("Relatório regenerado em docs/resultados/avaliacao.md (sem chamadas de API).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modos", nargs="+", choices=MODOS, default=list(MODOS))
    ap.add_argument("--limite", type=int, default=None, help="roda só as N primeiras perguntas")
    ap.add_argument("--so-relatorio", action="store_true")
    args = ap.parse_args(argv)
    if args.so_relatorio:
        return _so_relatorio()

    from ..agentes.anthropic_agente import AgenteAnthropic
    from ..agentes.openai_agente import AgenteOpenAI
    from ..agentes.prompts import carregar_prompt
    from ..ingestao.embeddings import OpenAIEmbedder
    from ..ingestao.indexador import carregar_indice
    from ..orquestrador.orquestrador import LogRoteamento, Orquestrador
    from ..orquestrador.politica import Politica, ordem_por_preco
    from ..recuperacao.buscador import Buscador

    try:
        s = carregar_settings()
    except ConfigError as e:
        print(f"ERRO de configuração: {e}")
        return 2
    tabela = TabelaPrecos.de_json(s.precos_path)
    controle = ControleCusto(tabela, s.orcamentos(), s.log_dir / "chamadas.jsonl")
    buscador = Buscador(carregar_indice(RAIZ / "indice"), OpenAIEmbedder(s, controle))
    prompt = carregar_prompt()
    ag = {"openai": AgenteOpenAI(s, controle, buscador, tabela, prompt),
          "anthropic": AgenteAnthropic(s, controle, buscador, tabela, prompt)}
    modelos = {"openai": s.openai_model, "anthropic": s.anthropic_model}
    pol = Politica.de_settings(s)
    perguntas = json.loads(PERGUNTAS.read_text(encoding="utf-8"))
    n_gabarito = len(perguntas)
    if args.limite:
        perguntas = perguntas[: args.limite]
    fatos, manual = carregar_fatos(FATOS), carregar_manual(MANUAL)

    # Em execução parcial, preserva os modos já medidos em execuções anteriores.
    arq = SAIDA / "avaliacao.json"
    anterior = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() and not args.limite else {}
    linhas: dict[str, list[Linha]] = {m: recalcular(ls, json.loads(PERGUNTAS.read_text(encoding="utf-8")), fatos, manual)
                                      for m, ls in anterior.get("linhas", {}).items() if m not in args.modos}
    print(f"prompt={prompt.versao} | perguntas={len(perguntas)} | modos={', '.join(args.modos)} | "
          f"preços de {tabela.data_consulta}")
    for modo in args.modos:
        if modo == "orquestrado":
            agentes, ordem = ag, ordem_por_preco(tabela, modelos)
        else:
            agentes, ordem = {modo: ag[modo]}, (modo,)
        orq = Orquestrador(agentes, ordem, pol, LogRoteamento(s.log_dir / f"avaliacao_{modo}_roteamento.jsonl"))
        parcial: list[Linha] = []

        def ao_terminar(l: Linha, parcial=parcial, modo=modo) -> None:
            parcial.append(l)
            marca = "acerto" if l.acerto else "ERRO  "
            print(f"[{modo}] {l.pergunta_id} {marca} valido={l.valido} final={l.provedor_final} "
                  f"custo={l.custo_usd:.6f} t={l.latencia_s:.1f}s")
            SAIDA.mkdir(parents=True, exist_ok=True)
            (SAIDA / f"avaliacao_{modo}.json").write_text(
                json.dumps([x.para_dict() for x in parcial], ensure_ascii=False, indent=1), encoding="utf-8")

        linhas[modo] = executar_modo(modo, perguntas, fatos, orq, manual, ao_terminar)

    resumos = {m: agregar(m, ls, n_gabarito) for m, ls in linhas.items()}
    meta = {"data": time.strftime("%Y-%m-%d"), "prompt_versao": prompt.versao, "prompt_sha": prompt.sha,
            "data_precos": tabela.data_consulta, "n_gabarito": n_gabarito, "limite_de_perguntas": args.limite,
            "modo_orquestracao": pol.modo,
            "precos": precos_dos_modos(tabela, modelos)}
    _escrever(resumos, linhas, meta)
    print("\nResultados em docs/resultados/avaliacao.md")
    for m, r in resumos.items():
        print(f"{m}: acerto {r.acertos}/{r.n_gabarito} | citação válida {r.validas}/{r.n_gabarito} | "
              f"custo/resposta US$ {r.custo_por_resposta_usd:.6f} | latência média {r.latencia_media_s:.2f}s")
    for p in ("openai", "anthropic"):
        print(f"gasto acumulado {p}: {controle.gasto(p):.6f} / teto {controle.orcamentos[p]:.2f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
