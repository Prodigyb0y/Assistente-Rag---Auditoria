"""Análise descritiva de logs/roteamento.jsonl: quantas perguntas seguiram cada caminho e quanto cada um custou.

NÃO usa IA e não chama nenhuma API: só lê o arquivo de log e agrupa os eventos `final`. É estatística
descritiva; não testa hipótese nem estima o que aconteceria em outras perguntas.

Limites do dado de origem (também impressos no relatório):
  * o log acumula execuções de dias, modos e configurações diferentes, e a confiança mínima de cada execução
    não é gravada;
  * a mesma pergunta repetida em duas execuções aparece duas vezes;
  * eventos de versões antigas do código não têm os campos `modo` e `caminho`.

Uso:
  python -m src.analise.roteamento                       # imprime o relatório
  python -m src.analise.roteamento --saida docs/resultados/analise_roteamento.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..config import RAIZ

LOG_PADRAO = RAIZ / "logs" / "roteamento.jsonl"
SEM_REGISTRO = "(sem registro)"


@dataclass
class Grupo:
    n: int = 0
    custo: float = 0.0
    latencia: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def somar(self, ev: dict[str, Any]) -> None:
        self.n += 1
        self.custo += float(ev.get("custo_usd") or 0.0)
        self.latencia += float(ev.get("latencia_s") or 0.0)
        self.tokens_in += int(ev.get("tokens_in") or 0)
        self.tokens_out += int(ev.get("tokens_out") or 0)

    @property
    def custo_medio(self) -> float:
        return self.custo / self.n if self.n else 0.0

    @property
    def latencia_media(self) -> float:
        return self.latencia / self.n if self.n else 0.0


@dataclass
class Analise:
    n_linhas: int = 0
    n_invalidas: int = 0
    finais: int = 0
    primeiro_ts: str | None = None
    ultimo_ts: str | None = None
    por_status: dict[str, Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    por_modo_status: dict[tuple[str, str], Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    por_motivo: dict[str, Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    por_caminho: dict[str, Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    por_provedor_final: dict[str, Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    por_n_provedores: dict[int, Grupo] = field(default_factory=lambda: defaultdict(Grupo))
    concordancias: Counter = field(default_factory=Counter)
    total: Grupo = field(default_factory=Grupo)


def carregar(caminho: Path) -> tuple[list[dict[str, Any]], int]:
    """Lê o JSONL; linhas vazias são ignoradas e linhas que não são JSON objeto são contadas como inválidas."""
    eventos: list[dict[str, Any]] = []
    invalidas = 0
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            ev = json.loads(linha)
        except json.JSONDecodeError:
            invalidas += 1
            continue
        if isinstance(ev, dict):
            eventos.append(ev)
        else:
            invalidas += 1
    return eventos, invalidas


def analisar(eventos: Iterable[dict[str, Any]], n_invalidas: int = 0) -> Analise:
    a = Analise(n_invalidas=n_invalidas)
    for ev in eventos:
        a.n_linhas += 1
        if ev.get("evento") == "decisao" and ev.get("acao") == "decidir_par":
            a.concordancias[ev.get("concordancia") or "não comparado"] += 1
        if ev.get("evento") != "final":
            continue
        a.finais += 1
        ts = ev.get("ts")
        if ts:
            a.primeiro_ts = min(a.primeiro_ts or ts, ts)
            a.ultimo_ts = max(a.ultimo_ts or ts, ts)
        status = ev.get("status") or SEM_REGISTRO
        modo = ev.get("modo") or SEM_REGISTRO
        motivo = ev.get("motivo_escalonamento") or "nenhum (aceito no primeiro)"
        caminho = ev.get("caminho") or SEM_REGISTRO
        provedor = ev.get("provedor_final") or "nenhum"
        n_prov = len(ev.get("rota") or [])
        for grupo in (a.total, a.por_status[status], a.por_modo_status[(modo, status)], a.por_motivo[motivo],
                      a.por_caminho[caminho], a.por_provedor_final[provedor], a.por_n_provedores[n_prov]):
            grupo.somar(ev)
    return a


def _tabela(titulo_col: str, linhas: list[tuple[str, Grupo]]) -> list[str]:
    out = [f"| {titulo_col} | Perguntas | Custo total (US$) | Custo médio (US$) | Latência média (s) |",
           "|---|---|---|---|---|"]
    for nome, g in sorted(linhas, key=lambda x: (-x[1].n, x[0])):
        out.append(f"| {nome} | {g.n} | {g.custo:.6f} | {g.custo_medio:.6f} | {g.latencia_media:.1f} |")
    return out


def gerar_markdown(a: Analise, origem: str = "logs/roteamento.jsonl") -> str:
    out = ["# Análise do log de roteamento (gerada por script)", "",
           f"> Gerado por `python -m src.analise.roteamento` a partir de `{origem}`. Análise **descritiva, sem IA**: "
           "conta eventos `final` e soma custo e latência. Não testa hipótese nem prevê outras perguntas.", ""]
    out += ["## Escopo do dado", "",
            f"- Linhas lidas: {a.n_linhas} (inválidas ignoradas: {a.n_invalidas}); perguntas finais (`final`): {a.finais}.",
            f"- Período: {a.primeiro_ts or '-'} a {a.ultimo_ts or '-'}.",
            f"- Custo total dessas perguntas: US$ {a.total.custo:.6f}; tokens: {a.total.tokens_in} de entrada e "
            f"{a.total.tokens_out} de saída.", ""]
    out += ["## Por estado final", ""] + _tabela("Estado", list(a.por_status.items())) + [""]
    out += ["## Por modo e estado final", ""] + _tabela(
        "Modo / estado", [(f"{m} / {s}", g) for (m, s), g in a.por_modo_status.items()]) + [""]
    out += ["## Por motivo de escalonamento (o que impediu aceitar a primeira resposta)", ""]
    out += _tabela("Motivo", list(a.por_motivo.items())) + [""]
    out += ["## Por caminho", ""] + _tabela("Caminho", list(a.por_caminho.items())) + [""]
    out += ["## Por provedor da resposta final", ""] + _tabela(
        "Provedor", list(a.por_provedor_final.items())) + [""]
    out += ["## Custo de chamar mais de um provedor", ""] + _tabela(
        "Provedores chamados", [(str(n), g) for n, g in a.por_n_provedores.items()]) + [""]
    if a.concordancias:
        out += ["## Comparação entre os dois provedores (eventos `decidir_par`)", "",
                "| Resultado | Eventos |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in a.concordancias.most_common()]
        out += [""]
    out += ["## Limites desta análise", "",
            "- O log acumula execuções de datas, modos e configurações diferentes; a confiança mínima de cada execução "
            "não é gravada, então não dá para separar execuções feitas com `media` das feitas com `alta`.",
            "- A mesma pergunta pode aparecer mais de uma vez (execuções repetidas) e é contada cada vez.",
            f"- Eventos sem os campos `modo` e `caminho` aparecem como \"{SEM_REGISTRO}\" e vêm de versões anteriores do código.",
            "- Os grupos são pequenos; as médias descrevem estas execuções e não permitem concluir sobre a frequência "
            "esperada em outras perguntas.", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--log", type=Path, default=LOG_PADRAO)
    ap.add_argument("--saida", type=Path, default=None, help="grava o relatório em markdown neste arquivo")
    args = ap.parse_args(argv)
    if not args.log.exists():
        print(f"ERRO: log não encontrado: {args.log}")
        return 2
    eventos, invalidas = carregar(args.log)
    try:
        origem = str(args.log.resolve().relative_to(RAIZ))
    except ValueError:
        origem = args.log.name
    md = gerar_markdown(analisar(eventos, invalidas), origem.replace("\\", "/"))
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(md, encoding="utf-8")
        print(f"Relatório gravado em {args.saida}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
