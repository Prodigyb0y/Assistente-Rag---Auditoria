"""Gera docs/resultados/avaliacao.md e avaliacao.json a partir dos resultados medidos.

Tudo que aparece em números vem de `Resumo`/`Linha`; o texto só descreve o método e os limites.
Se a regra de acerto ou o preço tiverem ressalvas, elas entram no relatório automaticamente.
"""
from __future__ import annotations

from typing import Any, Mapping

from .harness import MODOS, Linha, Resumo

ROTULO = {"openai": "Só OpenAI", "anthropic": "Só Anthropic", "orquestrado": "Orquestrado"}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _trecho(texto: str, n: int = 150) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def gerar_markdown(resumos: Mapping[str, Resumo], linhas: Mapping[str, list[Linha]], meta: Mapping[str, Any]) -> str:
    modos = [m for m in MODOS if m in resumos]
    out: list[str] = []
    out.append("# Resultados da avaliação (gerado por script)\n")
    out.append("> Arquivo gerado por `python -m src.avaliacao.executar`. Não edite à mão: rode o script de novo.\n")
    out.append(f"- Data da execução: **{meta['data']}**")
    out.append(f"- Prompt: `{meta['prompt_versao']}` (sha `{meta['prompt_sha']}`)")
    out.append(f"- Modelos: " + ", ".join(f"{p['provedor']}=`{p['modelo']}`" for p in meta["precos"]))
    if meta.get("modo_orquestracao"):
        out.append(f"- Modo de orquestração (modo orquestrado): **{meta['modo_orquestracao']}**")
    out.append(f"- Preços: tabela `config/precos.json` consultada em **{meta['data_precos']}**")
    out.append(f"- Base: dados **fictícios** (Gutenberg Systems), {meta['n_gabarito']} perguntas com gabarito\n")

    out.append("## Tabela de resultados\n")
    out.append("| Modo | Acerto | Citação válida | Cita a seção do gabarito | Custo por resposta (US$) | "
               "Latência média (s) | Latência mediana (s) | Respondidas |")
    out.append("|---|---|---|---|---|---|---|---|")
    for m in modos:
        r = resumos[m]
        out.append(f"| {ROTULO[m]} | {r.acertos}/{r.n_gabarito} ({_pct(r.acerto)}) | "
                   f"{r.validas}/{r.n_gabarito} ({_pct(r.citacao_valida)}) | "
                   f"{r.cita_origem}/{r.n_gabarito} ({_pct(r.taxa_cita_origem)}) | "
                   f"{r.custo_por_resposta_usd:.6f} | {r.latencia_media_s:.2f} | {r.latencia_mediana_s:.2f} | "
                   f"{r.n_executadas}/{r.n_gabarito} |")
    out.append("")
    out.append("| Modo | Custo total (US$) | Tokens de entrada | Tokens de saída | Latência máxima (s) | "
               "Respostas escalonadas | Tentativas extras (retry) | Resposta final por provedor |")
    out.append("|---|---|---|---|---|---|---|---|")
    for m in modos:
        r = resumos[m]
        provs = ", ".join(f"{k}: {v}" for k, v in sorted(r.finais_por_provedor.items())) or "-"
        out.append(f"| {ROTULO[m]} | {r.custo_total_usd:.6f} | {r.tokens_in} | {r.tokens_out} | "
                   f"{r.latencia_max_s:.2f} | {r.escalonadas} | {r.tentativas_extras} | {provs} |")
    out.append("")

    out.append("## Como cada métrica foi medida\n")
    out.append("- **Acerto**: respostas corretas ÷ perguntas do gabarito. Uma resposta é correta se o agente respondeu "
               "(`encontrado=true`) e o texto contém todos os fatos-chave da pergunta (`dados/fatos_chave.json`, "
               "derivados do gabarito), comparados sem acento e sem diferença de maiúsculas, em palavra inteira.")
    out.append("- **Citação válida**: saída em JSON conforme o schema e todas as citações entre os trechos que o "
               "agente de fato recuperou nessa execução. Não significa que a resposta esteja correta.")
    out.append("- **Cita a seção do gabarito**: a seção de origem do gabarito está entre as citadas.")
    out.append(f"- **Custo por resposta**: tokens de entrada e saída reais de cada chamada × preço da tabela "
               f"(consulta em {meta['data_precos']}), somando a busca (embedding da consulta) e **todas** as "
               "tentativas e provedores usados naquela pergunta, ÷ respostas obtidas.")
    out.append("- **Latência**: `time.perf_counter()` da chegada da pergunta até a resposta final, incluindo busca, "
               "chamadas ao modelo, esperas de retry e, no modo orquestrado, o segundo provedor quando chamado.")
    out.append("- Os três modos passam pelo mesmo orquestrador; os modos de provedor único têm retry, mas não fallback.\n")

    out.append("## Limites e ressalvas\n")
    out.append("- **Uma única execução por modo**: sem repetição, não há intervalo de confiança. Latência varia com a rede "
               "e a primeira chamada de uma execução costuma ser mais lenta (conexão fria). Prefira a mediana.")
    out.append("- A regra de acerto confere a **presença** dos fatos esperados, não a **ausência** de fatos errados, "
               "nem entende negação. A seção \"Auditoria do acerto\" lista cada resposta para revisão humana.")
    total_manual = sum(r.sobrescritas_manuais for r in resumos.values())
    out.append(f"- Sobrescritas manuais de acerto (`dados/acerto_manual.json`): **{total_manual}**.")
    nao_oficiais = [p for p in meta["precos"] if not p["verificado_oficial"]]
    for p in nao_oficiais:
        out.append(f"- **O preço de `{p['modelo']}` (US$ {p['input_mtok']}/{p['output_mtok']} por 1M de tokens) NÃO foi "
                   "confirmado na página oficial do provedor no momento desta execução.** Os custos da OpenAI e do modo "
                   "orquestrado usam esse preço. Depois da execução, o autor conferiu a página oficial em 2026-11-19; "
                   "a fonte está em `config/precos.json`.")
    out.append("- Base pequena, fictícia e com vocabulário compartilhado entre as perguntas e os documentos: os números "
               "não se generalizam para documentos reais.")
    out.append("- Gemini não faz parte deste projeto (restrição de escopo): é uma lacuna a fechar depois.\n")

    out.append("## Auditoria do acerto (por pergunta)\n")
    out.append("| Pergunta | " + " | ".join(ROTULO[m] for m in modos) + " |")
    out.append("|---|" + "---|" * len(modos))
    ids = [l.pergunta_id for l in linhas[modos[0]]]
    mapa = {m: {l.pergunta_id: l for l in linhas[m]} for m in modos}
    for i in ids:
        cel = []
        for m in modos:
            l = mapa[m].get(i)
            if l is None or not l.executada:
                cel.append("sem resposta")
            else:
                cel.append(("✓" if l.acerto else "✗") + (" (manual)" if l.acerto_origem == "manual" else "")
                           + (f" ←{l.provedor_final}" if m == "orquestrado" else ""))
        out.append(f"| {i} | " + " | ".join(cel) + " |")
    out.append("")
    reprovadas = [(m, l) for m in modos for l in linhas[m] if not l.acerto]
    if reprovadas:
        out.append("### Respostas reprovadas pela regra (revise antes de confiar no número)\n")
        for m, l in reprovadas:
            texto = l.resposta["resposta"] if l.resposta else (l.erro or "-")
            out.append(f"- {ROTULO[m]} {l.pergunta_id}: {_trecho(texto)}")
        out.append("")
    return "\n".join(out) + "\n"


def para_json(resumos: Mapping[str, Resumo], linhas: Mapping[str, list[Linha]], meta: Mapping[str, Any]) -> dict:
    return {
        "meta": dict(meta),
        "resumos": {m: {**r.__dict__, "acerto": r.acerto, "citacao_valida": r.citacao_valida,
                        "taxa_cita_origem": r.taxa_cita_origem} for m, r in resumos.items()},
        "linhas": {m: [l.para_dict() for l in ls] for m, ls in linhas.items()},
    }
