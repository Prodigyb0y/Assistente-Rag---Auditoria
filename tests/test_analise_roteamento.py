"""Análise descritiva do log de roteamento: sem rede, sem IA, com logs sintéticos."""
import json

import pytest

from src.analise.roteamento import SEM_REGISTRO, analisar, carregar, gerar_markdown, main


def final(pid, status, rota, custo, lat, motivo=None, modo="adaptativo", caminho="direto", tin=100, tout=10, **kw):
    ev = {"ts": "2026-11-19T10:00:00-0300", "evento": "final", "pergunta_id": pid, "status": status,
          "provedor_final": rota[-1] if rota else None, "rota": rota, "motivo_escalonamento": motivo,
          "prompt_versao": "agente_resposta_v1", "tentativas": len(rota), "tokens_in": tin, "tokens_out": tout,
          "custo_usd": custo, "latencia_s": lat}
    if modo:
        ev["modo"] = modo
    if caminho:
        ev["caminho"] = caminho
    ev.update(kw)
    return ev


EVENTOS = [
    final("A", "aceita_no_primeiro", ["anthropic"], 0.0005, 2.0),
    final("B", "aceita_no_primeiro", ["anthropic"], 0.0007, 4.0),
    final("C", "nao_encontrado_confirmado", ["anthropic", "openai"], 0.005, 15.0, motivo="nao_encontrado",
          caminho="segunda_opiniao"),
    final("D", "aceita_por_consenso", ["anthropic", "openai"], 0.004, 12.0, motivo="confianca_baixa",
          caminho="confirmacao_cruzada"),
    final("E", "melhor_esforco", ["anthropic", "openai"], 0.003, 9.0, motivo="sem_citacao_valida", modo=None, caminho=None),
    {"ts": "2026-11-19T10:00:01-0300", "evento": "decisao", "acao": "decidir_par", "concordancia": "concordam"},
    {"ts": "2026-11-19T10:00:02-0300", "evento": "decisao", "acao": "decidir_par", "concordancia": None},
    {"ts": "2026-11-19T10:00:03-0300", "evento": "tentativa", "pergunta_id": "A"},
]


def test_conta_perguntas_custo_e_latencia_por_estado():
    a = analisar(EVENTOS)
    assert a.finais == 5 and a.total.custo == pytest.approx(0.0132)
    g = a.por_status["aceita_no_primeiro"]
    assert g.n == 2 and g.custo == pytest.approx(0.0012) and g.custo_medio == pytest.approx(0.0006)
    assert g.latencia_media == pytest.approx(3.0)


def test_agrupa_por_motivo_e_marca_os_aceitos_no_primeiro():
    a = analisar(EVENTOS)
    assert a.por_motivo["nenhum (aceito no primeiro)"].n == 2
    assert a.por_motivo["nao_encontrado"].custo == pytest.approx(0.005)
    assert a.por_motivo["confianca_baixa"].n == 1


def test_custo_de_chamar_dois_provedores_separado_do_de_um():
    a = analisar(EVENTOS)
    assert a.por_n_provedores[1].n == 2 and a.por_n_provedores[2].n == 3
    assert a.por_n_provedores[2].custo_medio == pytest.approx(0.004)


def test_eventos_antigos_sem_modo_e_caminho_ficam_sem_registro():
    a = analisar(EVENTOS)
    assert a.por_modo_status[(SEM_REGISTRO, "melhor_esforco")].n == 1 and a.por_caminho[SEM_REGISTRO].n == 1


def test_conta_a_comparacao_entre_provedores():
    a = analisar(EVENTOS)
    assert a.concordancias["concordam"] == 1 and a.concordancias["não comparado"] == 1


def test_carregar_ignora_linhas_vazias_e_conta_invalidas(tmp_path):
    arq = tmp_path / "r.jsonl"
    arq.write_text(json.dumps(EVENTOS[0]) + "\n\n{quebrado\n[1, 2]\n" + json.dumps(EVENTOS[1]) + "\n", encoding="utf-8")
    eventos, invalidas = carregar(arq)
    assert len(eventos) == 2 and invalidas == 2


def test_relatorio_traz_limites_e_nao_afirma_causa():
    md = gerar_markdown(analisar(EVENTOS, 0))
    assert "sem IA" in md and "Limites desta análise" in md and "confiança mínima" in md
    assert "| nao_encontrado |" in md and "| 2 |" in md


def test_cli_grava_o_relatorio_e_falha_sem_log(tmp_path, capsys):
    log = tmp_path / "r.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in EVENTOS) + "\n", encoding="utf-8")
    saida = tmp_path / "out" / "analise.md"
    assert main(["--log", str(log), "--saida", str(saida)]) == 0 and "Por estado final" in saida.read_text(encoding="utf-8")
    assert main(["--log", str(tmp_path / "nao_existe.jsonl")]) == 2
