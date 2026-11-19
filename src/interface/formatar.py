"""Texto exibido na tela, separado da biblioteca de interface para ser testável."""
from __future__ import annotations

from .servico import RespostaDemo

CONFIANCA = {"alta": "alta", "media": "média", "baixa": "baixa"}
AVISO = ("**Demo com dados 100% fictícios** (Gutenberg Systems). Não digite dados reais de nenhuma empresa. "
         "A resposta é apoio à busca em documentos: **não é decisão de auditoria**. Confira sempre a fonte citada.")


def formatar(r: RespostaDemo) -> tuple[str, str]:
    """(texto principal, linha de detalhes), ambos em Markdown."""
    if not r.ok:
        return f"**{r.mensagem}**", f"Perguntas restantes para você hoje: {r.restantes_visitante}"
    if r.encontrado is False:
        principal = f"{r.resposta}\n\n_A base não traz essa informação com segurança._"
    else:
        principal = r.resposta or ""
    fontes = ", ".join(f"`{c['documento']} / {c['secao']}`" for c in r.citacoes) or "nenhuma"
    principal += f"\n\n**Fontes citadas:** {fontes}"
    if not r.aceita_pela_regra:
        principal += "\n\n_Atenção: nenhum dos provedores passou na regra de qualidade; esta é a melhor resposta obtida._"
    origem = "resposta em cache (sem custo)" if r.status == "cache" else \
        f"provedor: {r.provedor} · custo: US$ {r.custo_usd:.6f} · {r.latencia_s:.1f}s"
    detalhes = (f"Confiança declarada pelo agente: {CONFIANCA.get(r.confianca or '', '-')} · {origem} · "
                f"perguntas restantes para você hoje: {r.restantes_visitante}")
    return principal, detalhes
