"""Modos adaptativo e consenso: decisão sobre o par de respostas e fluxo do orquestrador.

Tudo offline, com agentes e relógio falsos. Estes testes provam a LÓGICA de decisão. O comportamento dos
modelos reais nesses caminhos só se mede rodando as perguntas de dados/perguntas_orquestracao.json.
"""
import pytest

from src.custo import OrcamentoExcedido
from src.orquestrador.orquestrador import (ACEITA_APOS_ESCALONAMENTO, ACEITA_NO_PRIMEIRO, ACEITA_POR_CONSENSO,
                                           DIVERGENCIA, FALHA, MELHOR_ESFORCO, NAO_ENCONTRADO_CONFIRMADO,
                                           LogRoteamento, Orquestrador)
from src.orquestrador.politica import Concordancia, Politica, comparar, decidir_par, numeros
from tests.test_orquestrador import AgenteFalso, Relogio, ler, montar, ok
from tests.test_roteamento import resultado

ACE3 = (("POL-ACE", "ACE-3"),)


def com_texto(prov, texto, **kw):
    r = ok(prov, **kw)
    r.resposta = r.resposta.model_copy(update={"resposta": texto})
    return r


def abstem(prov):
    return ok(prov, encontrado=False, citacoes=(), confianca="baixa")


# --- números e comparação ------------------------------------------------------------------------

def test_numeros_ignora_ponto_de_milhar():
    assert numeros("acima de R$ 100.000,00") == numeros("acima de 100000,00")
    assert numeros("a cada 90 dias") != numeros("a cada 60 dias")


def test_comparar_mesmas_fontes_e_numeros_concordam():
    a, b = com_texto("anthropic", "A cada 90 dias.", citacoes=ACE3), com_texto("openai", "90 dias, pelo Dono.", citacoes=ACE3)
    assert comparar(a, b) is Concordancia.CONCORDAM


def test_comparar_fontes_contidas_concordam():
    a = com_texto("anthropic", "90 dias", citacoes=ACE3)
    b = com_texto("openai", "90 dias", citacoes=ACE3 + (("POL-ACE", "ACE-4"),))
    assert comparar(a, b) is Concordancia.CONCORDAM


def test_comparar_fontes_disjuntas_divergem():
    a = com_texto("anthropic", "90 dias", citacoes=ACE3)
    b = com_texto("openai", "90 dias", citacoes=(("POL-LOG", "LOG-3"),))
    assert comparar(a, b) is Concordancia.DIVERGEM


def test_comparar_numeros_diferentes_divergem_mesmo_com_a_mesma_fonte():
    a, b = com_texto("anthropic", "90 dias", citacoes=ACE3), com_texto("openai", "60 dias", citacoes=ACE3)
    assert comparar(a, b) is Concordancia.DIVERGEM


# --- decidir_par: cada caminho -------------------------------------------------------------------

def test_a_aceito_e_sem_segundo_fica_com_a():
    d = decidir_par(ok("anthropic"), None)
    assert (d.status, d.escolhido) == (ACEITA_NO_PRIMEIRO, "a")


def test_abstencao_sem_segundo_nao_e_aceita():
    d = decidir_par(abstem("anthropic"), None)
    assert d.status == MELHOR_ESFORCO and d.motivo == "nao_encontrado"


def test_abstencao_e_segundo_encontra_aceita_o_segundo():
    d = decidir_par(abstem("anthropic"), ok("openai"))
    assert (d.status, d.escolhido, d.motivo) == (ACEITA_APOS_ESCALONAMENTO, "b", "nao_encontrado")


def test_duas_abstencoes_confirmam_que_a_base_nao_traz():
    d = decidir_par(abstem("anthropic"), abstem("openai"))
    assert (d.status, d.escolhido) == (NAO_ENCONTRADO_CONFIRMADO, "a")


def test_duas_respostas_validas_que_concordam_viram_consenso():
    a, b = com_texto("anthropic", "90 dias", citacoes=ACE3), com_texto("openai", "90 dias", citacoes=ACE3)
    d = decidir_par(a, b)
    assert d.status == ACEITA_POR_CONSENSO and d.concordancia is Concordancia.CONCORDAM


def test_duas_respostas_validas_que_divergem_sinalizam_divergencia():
    a, b = com_texto("anthropic", "90 dias", citacoes=ACE3), com_texto("openai", "60 dias", citacoes=ACE3)
    d = decidir_par(a, b)
    assert d.status == DIVERGENCIA and d.concordancia is Concordancia.DIVERGEM


def test_media_e_media_com_minima_alta_concordando_viram_consenso():
    a = com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)
    b = com_texto("openai", "24 horas", confianca="media", citacoes=ACE3)
    d = decidir_par(a, b, "alta")
    assert d.status == ACEITA_POR_CONSENSO and d.motivo == "confianca_baixa"


def test_media_e_media_com_minima_alta_divergindo_sinalizam_divergencia():
    a = com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)
    b = com_texto("openai", "48 horas", confianca="media", citacoes=ACE3)
    assert decidir_par(a, b, "alta").status == DIVERGENCIA


def test_baixa_nos_dois_nao_forma_consenso():
    a = com_texto("anthropic", "24 horas", confianca="baixa", citacoes=ACE3)
    b = com_texto("openai", "24 horas", confianca="baixa", citacoes=ACE3)
    assert decidir_par(a, b, "media").status == MELHOR_ESFORCO


def test_primeiro_media_valido_e_segundo_alto_diferente_sinaliza_divergencia_e_fica_com_o_segundo():
    a = com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)
    b = com_texto("openai", "48 horas", confianca="alta", citacoes=ACE3)
    d = decidir_par(a, b, "alta")
    assert (d.status, d.escolhido) == (DIVERGENCIA, "b")


def test_primeiro_media_e_segundo_alto_igual_aceita_o_segundo():
    a = com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)
    b = com_texto("openai", "24 horas", confianca="alta", citacoes=ACE3)
    d = decidir_par(a, b, "alta")
    assert (d.status, d.escolhido) == (ACEITA_APOS_ESCALONAMENTO, "b")


def test_primeiro_aceito_e_segundo_se_abstem_fica_com_o_primeiro():
    d = decidir_par(ok("anthropic"), abstem("openai"))
    assert (d.status, d.escolhido) == (ACEITA_NO_PRIMEIRO, "a")


def test_citacao_inventada_no_primeiro_e_segundo_bom_aceita_o_segundo():
    ruim = ok("anthropic", citacoes_ok=False, erro="citação fora dos trechos recuperados: POL-X/X-1")
    d = decidir_par(ruim, ok("openai"))
    assert (d.status, d.escolhido, d.motivo) == (ACEITA_APOS_ESCALONAMENTO, "b", "sem_citacao_valida")


def test_dois_resultados_ruins_viram_melhor_esforco():
    ruim = lambda p: ok(p, citacoes_ok=False, erro="citação fora dos trechos recuperados: POL-X/X-1")  # noqa: E731
    assert decidir_par(ruim("anthropic"), ruim("openai")).status == MELHOR_ESFORCO


# --- orquestrador: modo adaptativo ---------------------------------------------------------------

def adaptativo(tmp_path, barato, caro, modo="adaptativo", **pol):
    return montar(tmp_path, barato, caro, modo=modo, **pol)


def test_adaptativo_aceita_direto_e_nao_chama_o_segundo(tmp_path):
    b, c = AgenteFalso("anthropic", [ok("anthropic")]), AgenteFalso("openai", [])
    orq, _, _ = adaptativo(tmp_path, b, c)
    res = orq.responder("p", "Q")
    assert res.status == ACEITA_NO_PRIMEIRO and res.caminho == "direto" and c.chamadas == 0


def test_adaptativo_primeiro_se_abstem_e_o_openai_encontra_e_e_aceito(tmp_path):
    """O caminho que a rodada real de 2026-11-19 não exercitou: resposta do OpenAI aceita pelo orquestrador."""
    b, c = AgenteFalso("anthropic", [abstem("anthropic")]), AgenteFalso("openai", [ok("openai")])
    orq, _, log = adaptativo(tmp_path, b, c)
    res = orq.responder("p", "Q")
    assert res.status == ACEITA_APOS_ESCALONAMENTO and res.provedor_final == "openai" and res.aceito
    assert res.caminho == "segunda_opiniao" and res.motivo_escalonamento == "nao_encontrado" and res.escalou
    final = [e for e in ler(log) if e["evento"] == "final"][0]
    assert final["modo"] == "adaptativo" and final["caminho"] == "segunda_opiniao"


def test_adaptativo_duas_abstencoes_sao_aceitas_como_nao_encontrado_confirmado(tmp_path):
    b, c = AgenteFalso("anthropic", [abstem("anthropic")]), AgenteFalso("openai", [abstem("openai")])
    orq, _, _ = adaptativo(tmp_path, b, c)
    res = orq.responder("p", "Q")
    assert res.status == NAO_ENCONTRADO_CONFIRMADO and res.aceito and res.provedor_final == "anthropic"
    assert res.custo_total_usd == pytest.approx(0.002)   # pagou os dois: a confirmação não é de graça


def test_adaptativo_confianca_media_com_minima_alta_pede_confirmacao_cruzada(tmp_path):
    b = AgenteFalso("anthropic", [com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)])
    c = AgenteFalso("openai", [com_texto("openai", "24 horas", confianca="media", citacoes=ACE3)])
    orq, _, _ = adaptativo(tmp_path, b, c, confianca_minima="alta")
    res = orq.responder("p", "Q")
    assert res.status == ACEITA_POR_CONSENSO and res.caminho == "confirmacao_cruzada"
    assert res.concordancia == "concordam"


def test_adaptativo_confirmacao_cruzada_com_divergencia_nao_e_aceita(tmp_path):
    b = AgenteFalso("anthropic", [com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)])
    c = AgenteFalso("openai", [com_texto("openai", "48 horas", confianca="media", citacoes=ACE3)])
    orq, _, _ = adaptativo(tmp_path, b, c, confianca_minima="alta")
    res = orq.responder("p", "Q")
    assert res.status == DIVERGENCIA and not res.aceito and res.concordancia == "divergem"


def test_adaptativo_teto_do_primeiro_faz_o_segundo_assumir(tmp_path):
    b, c = AgenteFalso("anthropic", [OrcamentoExcedido("teto")]), AgenteFalso("openai", [ok("openai")])
    orq, _, _ = adaptativo(tmp_path, b, c)
    res = orq.responder("p", "Q")
    assert res.status == ACEITA_APOS_ESCALONAMENTO and res.provedor_final == "openai"
    assert res.motivo_escalonamento == "orcamento_excedido"


def test_adaptativo_teto_nos_dois_e_falha(tmp_path):
    b, c = AgenteFalso("anthropic", [OrcamentoExcedido("t")]), AgenteFalso("openai", [OrcamentoExcedido("t")])
    orq, _, _ = adaptativo(tmp_path, b, c)
    assert orq.responder("p", "Q").status == FALHA


def test_adaptativo_segundo_bloqueado_pelo_teto_deixa_melhor_esforco_para_abstencao(tmp_path):
    b, c = AgenteFalso("anthropic", [abstem("anthropic")]), AgenteFalso("openai", [OrcamentoExcedido("t")])
    orq, _, _ = adaptativo(tmp_path, b, c)
    res = orq.responder("p", "Q")
    assert res.status == MELHOR_ESFORCO and res.caminho == "segundo_indisponivel" and not res.aceito


# --- orquestrador: modo consenso -----------------------------------------------------------------

def test_consenso_sempre_chama_os_dois_e_aceita_quando_concordam(tmp_path):
    b = AgenteFalso("anthropic", [com_texto("anthropic", "90 dias", citacoes=ACE3)])
    c = AgenteFalso("openai", [com_texto("openai", "90 dias", citacoes=ACE3)])
    orq, _, _ = adaptativo(tmp_path, b, c, modo="consenso")
    res = orq.responder("p", "Q")
    assert b.chamadas == 1 and c.chamadas == 1
    assert res.status == ACEITA_POR_CONSENSO and res.custo_total_usd == pytest.approx(0.002)


def test_consenso_sinaliza_divergencia_mesmo_com_o_primeiro_aceito_pela_regra(tmp_path):
    b = AgenteFalso("anthropic", [com_texto("anthropic", "90 dias", citacoes=ACE3)])
    c = AgenteFalso("openai", [com_texto("openai", "60 dias", citacoes=ACE3)])
    orq, _, _ = adaptativo(tmp_path, b, c, modo="consenso")
    assert orq.responder("p", "Q").status == DIVERGENCIA


# --- configuração --------------------------------------------------------------------------------

def test_modo_invalido_e_recusado():
    with pytest.raises(ValueError):
        Politica(modo="aleatorio")


def test_adaptativo_com_um_provedor_so_usa_a_regra_original(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic")])
    rel = Relogio()
    orq = Orquestrador({"anthropic": b}, ["anthropic"], Politica(modo="adaptativo"),
                       LogRoteamento(tmp_path / "r.jsonl"), dormir=rel.dormir, relogio=rel.agora)
    assert orq.responder("p", "Q").status == ACEITA_NO_PRIMEIRO


def test_settings_le_o_modo_do_ambiente():
    from src.config import carregar_settings
    assert carregar_settings({"ORQUESTRACAO_MODO": "consenso"}, usar_dotenv=False).orquestracao_modo == "consenso"
    assert carregar_settings({}, usar_dotenv=False).orquestracao_modo == "adaptativo"
    assert Politica.de_settings(carregar_settings({"ORQUESTRACAO_MODO": "consenso"}, usar_dotenv=False)).modo == "consenso"


# --- perguntas de orquestração -------------------------------------------------------------------

def test_perguntas_de_orquestracao_apontam_para_secoes_que_existem():
    import json
    import re
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    secoes = {}
    for md in (raiz / "dados" / "documentos").glob("POL-*.md"):
        codigo = md.name.split("_")[0]
        secoes[codigo] = set(re.findall(r"^## ([A-Z]{3}-\d+)", md.read_text(encoding="utf-8"), re.M))
    qs = json.loads((raiz / "dados" / "perguntas_orquestracao.json").read_text(encoding="utf-8"))
    assert len({q["id"] for q in qs}) == len(qs) == 10
    for q in qs:
        assert q["revisado"] is False                      # o gabarito só vale depois da revisão do autor
        assert q["tipo"] in {"combina_secoes", "ambigua", "adjacente_fora_da_base"}
        for f in q["fontes"]:
            assert f["secao"] in secoes[f["documento"]], (q["id"], f)


def test_confirmacao_cruzada_registra_a_concordancia_mesmo_quando_so_o_segundo_passa_na_regra():
    """Caso observado na rodada real de 2026-11-19 (O02): o primeiro ficou abaixo da confiança mínima e o
    segundo foi aceito. O log mostrava concordância '-' mesmo tendo havido a comparação."""
    a = com_texto("anthropic", "24 horas", confianca="media", citacoes=ACE3)
    b = com_texto("openai", "24 horas", confianca="alta", citacoes=ACE3)
    d = decidir_par(a, b, "alta")
    assert d.status == ACEITA_APOS_ESCALONAMENTO and d.concordancia is Concordancia.CONCORDAM


def test_concordancia_tambem_e_registrada_quando_so_o_primeiro_passa_na_regra():
    a = com_texto("anthropic", "24 horas", confianca="alta", citacoes=ACE3)
    b = com_texto("openai", "24 horas", confianca="media", citacoes=ACE3)
    d = decidir_par(a, b, "alta")
    assert d.status == ACEITA_NO_PRIMEIRO and d.concordancia is Concordancia.CONCORDAM


def test_concordancia_fica_vazia_quando_o_segundo_se_abstem():
    d = decidir_par(ok("anthropic"), abstem("openai"))
    assert d.concordancia is None
