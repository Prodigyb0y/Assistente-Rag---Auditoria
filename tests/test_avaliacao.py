"""Testes da regra de acerto, do harness e do relatório. Offline: agentes falsos, sem custo.
Os números gerados aqui vêm de agentes falsos e NÃO são métricas do projeto."""
import json
from pathlib import Path

import pytest

from src.agentes.contrato import Citacao, ResultadoAgente, RespostaAuditoria
from src.avaliacao.acerto import (avaliar_acerto, carregar_fatos, carregar_manual, cita_origem, contem, normalizar)
from src.avaliacao.harness import (MODOS, agregar, executar_modo, precos_dos_modos, recalcular)
from src.avaliacao.relatorio import gerar_markdown, para_json
from src.custo import TabelaPrecos
from src.orquestrador.orquestrador import Orquestrador
from src.orquestrador.politica import Politica

PERGUNTAS = json.loads(Path("dados/perguntas.json").read_text(encoding="utf-8"))
FATOS = carregar_fatos(Path("dados/fatos_chave.json"))


def resp(texto, encontrado=True, cits=(("POL-ACE", "ACE-3"),), conf="alta"):
    return RespostaAuditoria(resposta=texto, encontrado=encontrado, confianca=conf,
                             citacoes=[Citacao(documento=d, secao=s) for d, s in cits])


# --- regra de acerto -----------------------------------------------------------------------

def test_fatos_cobrem_exatamente_as_30_perguntas():
    assert set(FATOS) == {q["id"] for q in PERGUNTAS} and len(FATOS) == 30
    assert all(grupos and all(g and all(isinstance(a, str) and a for a in g) for g in grupos)
               for grupos in FATOS.values())


@pytest.mark.parametrize("q", PERGUNTAS, ids=lambda q: q["id"])
def test_a_resposta_esperada_do_gabarito_passa_na_propria_regra(q):
    assert avaliar_acerto(resp(q["resposta_esperada"]), FATOS[q["id"]])


@pytest.mark.parametrize("qid,errada", [
    ("Q01", "A cada 60 dias, pelo gerente de TI."),
    ("Q02", "Em até 72 horas."),
    ("Q24", "Acima de R$ 10.000,00."),
    ("Q21", "A diretoria é avisada em 21 horas."),     # "1 hora" não casa com "21 horas"
    ("Q04", "Por 35 anos."),                            # "5 anos" não casa com "35 anos"
    ("Q10", "Às terças."),                              # falta "quintas"
    ("Q13", "Sim, sem exceções."),                      # falta 16h e CAB
    ("Q23", "Apenas S1, em 10 dias úteis."),            # falta S2
])
def test_respostas_erradas_ou_incompletas_reprovam(qid, errada):
    assert not avaliar_acerto(resp(errada), FATOS[qid])


def test_nao_encontrado_ou_sem_resposta_nunca_acerta():
    q = PERGUNTAS[0]
    assert not avaliar_acerto(None, FATOS[q["id"]])
    assert not avaliar_acerto(resp(q["resposta_esperada"], encontrado=False, cits=()), FATOS[q["id"]])


def test_normalizacao_e_palavra_inteira():
    assert normalizar("  Às  TERÇAS e quintas ") == "as tercas e quintas"
    assert contem(normalizar("revogados em até 24h"), "24h")
    assert not contem(normalizar("revogados em 124h"), "24h")
    assert contem(normalizar("R$ 100.000,00"), "100.000")
    assert contem(normalizar("dias úteis."), "dias uteis")


def test_sinonimos_do_grupo_valem():
    assert avaliar_acerto(resp("Em até 24h após a saída."), FATOS["Q02"])
    assert avaliar_acerto(resp("Em até 24 horas após a saída."), FATOS["Q02"])


def test_cita_origem():
    assert cita_origem(resp("x"), "POL-ACE", "ACE-3")
    assert not cita_origem(resp("x"), "POL-ACE", "ACE-4")
    assert not cita_origem(None, "POL-ACE", "ACE-3")


def test_manual_ausente_e_vazio_e_chaves_com_underscore_sao_ignoradas(tmp_path):
    assert carregar_manual(tmp_path / "nao_existe.json") == {}
    (tmp_path / "m.json").write_text(json.dumps({"_nota": "x", "openai:Q11": True}), encoding="utf-8")
    assert carregar_manual(tmp_path / "m.json") == {"openai:Q11": True}


# --- harness -------------------------------------------------------------------------------

class AgenteDoGabarito:
    """Responde com a resposta esperada do gabarito (ou errada em ids dados) e custo fixo."""

    def __init__(self, provedor, erradas=(), custo=0.001, lat=0.0, confianca="alta"):
        self.provedor, self.modelo = provedor, f"m-{provedor}"
        self.erradas, self.custo, self.confianca = set(erradas), custo, confianca
        self.por_pergunta = {q["pergunta"]: q for q in PERGUNTAS}

    def responder(self, pergunta, pergunta_id=""):
        q = self.por_pergunta[pergunta]
        texto = "resposta errada" if q["id"] in self.erradas else q["resposta_esperada"]
        r = ResultadoAgente(provedor=self.provedor, modelo=self.modelo, prompt_versao="v1", prompt_sha="s",
                            pergunta_id=pergunta_id, pergunta=pergunta, schema_ok=True, citacoes_ok=True,
                            resposta=resp(texto, cits=((q["documento"], q["secao"]),), conf=self.confianca))
        r.tokens_in, r.tokens_out, r.custo_llm_usd, r.latencia_s = 100, 10, self.custo, 0.5
        return r


def rodar(modo, agentes, ordem, manual=None, perguntas=PERGUNTAS):
    orq = Orquestrador(agentes, ordem, Politica(), dormir=lambda s: None)
    return executar_modo(modo, perguntas, FATOS, orq, manual or {})


def test_modo_unico_acerta_o_que_o_agente_acerta():
    ag = AgenteDoGabarito("openai", erradas={"Q01", "Q02"})
    linhas = rodar("openai", {"openai": ag}, ["openai"])
    r = agregar("openai", linhas, 30)
    assert r.acertos == 28 and r.validas == 30 and r.cita_origem == 30 and r.n_executadas == 30
    assert r.acerto == pytest.approx(28 / 30)
    assert r.custo_total_usd == pytest.approx(0.030) and r.custo_por_resposta_usd == pytest.approx(0.001)
    assert r.tokens_in == 3000 and r.tokens_out == 300
    assert [l.pergunta_id for l in linhas if not l.acerto] == ["Q01", "Q02"]


def test_orquestrado_escala_e_soma_custo_dos_dois_provedores():
    barato = AgenteDoGabarito("anthropic", erradas={"Q03"}, custo=0.0005, confianca="alta")
    # o barato acerta tudo com confiança alta, exceto Q03, onde o orquestrador NÃO escala (a regra olha
    # citação e confiança, não correção): este é exatamente o limite do roteamento que a tabela revela.
    caro = AgenteDoGabarito("openai", custo=0.002)
    linhas = rodar("orquestrado", {"anthropic": barato, "openai": caro}, ["anthropic", "openai"])
    r = agregar("orquestrado", linhas, 30)
    assert r.escalonadas == 0 and r.acertos == 29 and r.finais_por_provedor == {"anthropic": 30}
    assert r.custo_total_usd == pytest.approx(30 * 0.0005)


def test_orquestrado_escala_por_confianca_baixa_e_cobra_os_dois():
    barato = AgenteDoGabarito("anthropic", erradas={"Q03"}, custo=0.0005, confianca="baixa")
    caro = AgenteDoGabarito("openai", custo=0.002)
    linhas = rodar("orquestrado", {"anthropic": barato, "openai": caro}, ["anthropic", "openai"])
    r = agregar("orquestrado", linhas, 30)
    assert r.escalonadas == 30 and r.acertos == 30 and r.finais_por_provedor == {"openai": 30}
    assert r.custo_total_usd == pytest.approx(30 * (0.0005 + 0.002))
    assert all(l.rota == ["anthropic", "openai"] and l.motivo_escalonamento == "confianca_baixa" for l in linhas)


def test_denominador_e_o_gabarito_mesmo_com_execucao_parcial():
    ag = AgenteDoGabarito("openai")
    linhas = rodar("openai", {"openai": ag}, ["openai"], perguntas=PERGUNTAS[:3])
    r = agregar("openai", linhas, 30)
    assert r.n_executadas == 3 and r.acertos == 3 and r.acerto == pytest.approx(3 / 30)


def test_sobrescrita_manual_e_contada_e_marcada():
    ag = AgenteDoGabarito("openai", erradas={"Q05"})
    linhas = rodar("openai", {"openai": ag}, ["openai"], manual={"openai:Q05": True})
    q5 = next(l for l in linhas if l.pergunta_id == "Q05")
    assert q5.acerto and q5.acerto_origem == "manual"
    assert agregar("openai", linhas, 30).sobrescritas_manuais == 1


def test_recalcular_reaplica_regra_e_sobrescritas_sem_api():
    ag = AgenteDoGabarito("openai", erradas={"Q05"})
    salvas = [l.para_dict() for l in rodar("openai", {"openai": ag}, ["openai"])]
    assert sum(d["acerto"] for d in salvas) == 29
    novas = recalcular(salvas, PERGUNTAS, FATOS, {"openai:Q05": True})
    assert sum(l.acerto for l in novas) == 30


def test_latencia_mediana_media_e_max():
    from src.avaliacao.harness import Linha
    def lin(t):
        return Linha("openai", "Q", True, "s", "openai", True, True, "regra", True, 0.0, 0, 0, t, 1, [], None,
                     "v1", None)
    r = agregar("openai", [lin(1.0), lin(2.0), lin(9.0)], 3)
    assert r.latencia_media_s == pytest.approx(4.0) and r.latencia_mediana_s == 2.0 and r.latencia_max_s == 9.0


# --- relatório -----------------------------------------------------------------------------

def _meta(precos):
    return {"data": "2026-11-19", "prompt_versao": "agente_resposta_v1", "prompt_sha": "abc", "data_precos": "2026-11-19",
            "n_gabarito": 30, "limite_de_perguntas": None, "precos": precos}


def test_relatorio_gerado_traz_numeros_calculados_metodo_e_aviso_de_preco():
    tabela = TabelaPrecos.de_json("config/precos.json")
    precos = precos_dos_modos(tabela, {"openai": "gpt-6.1-terra", "anthropic": "claude-haiku-5-5"})
    for p in precos:   # o preço real já foi conferido; o teste força o caso não conferido de forma sintética
        if p["modelo"] == "gpt-6.1-terra":
            p["verificado_oficial"] = False
    ag_o = AgenteDoGabarito("openai", erradas={"Q01"}, custo=0.002)
    ag_a = AgenteDoGabarito("anthropic", custo=0.0005)
    linhas = {"openai": rodar("openai", {"openai": ag_o}, ["openai"]),
              "anthropic": rodar("anthropic", {"anthropic": ag_a}, ["anthropic"]),
              "orquestrado": rodar("orquestrado", {"anthropic": ag_a, "openai": ag_o}, ["anthropic", "openai"])}
    resumos = {m: agregar(m, ls, 30) for m, ls in linhas.items()}
    md = gerar_markdown(resumos, linhas, _meta(precos))
    assert "| Só OpenAI | 29/30 (96.7%)" in md and "| Só Anthropic | 30/30 (100.0%)" in md
    assert "0.002000" in md and "0.000500" in md                      # custo por resposta calculado
    assert "time.perf_counter()" in md and "2026-11-19" in md and "agente_resposta_v1" in md
    assert "NÃO foi confirmado" in md and "gpt-6.1-terra" in md        # preço não oficial é sinalizado
    assert "OpenAI e Anthropic" in md and "Gemini" not in md and "fictícios" in md and "Uma única execução" in md
    assert "Respostas reprovadas pela regra" in md and "Q01" in md
    j = para_json(resumos, linhas, _meta(precos))
    assert j["resumos"]["openai"]["acertos"] == 29 and len(j["linhas"]["orquestrado"]) == 30


def test_relatorio_sem_aviso_quando_todos_os_precos_sao_oficiais():
    precos = [{"provedor": "anthropic", "modelo": "x", "input_mtok": 1, "output_mtok": 2, "verificado_oficial": True}]
    ag = AgenteDoGabarito("anthropic")
    linhas = {"anthropic": rodar("anthropic", {"anthropic": ag}, ["anthropic"])}
    md = gerar_markdown({"anthropic": agregar("anthropic", linhas["anthropic"], 30)}, linhas, _meta(precos))
    assert "NÃO foi confirmado" not in md


def test_modos_conhecidos():
    assert MODOS == ("openai", "anthropic", "orquestrado")


def test_so_relatorio_regenera_sem_api_e_aplica_sobrescritas(tmp_path, monkeypatch):
    import src.avaliacao.executar as ex
    monkeypatch.setattr(ex, "SAIDA", tmp_path)
    monkeypatch.setattr(ex, "MANUAL", tmp_path / "acerto_manual.json")
    precos = [{"provedor": "openai", "modelo": "m", "input_mtok": 1, "output_mtok": 2, "verificado_oficial": True}]
    ag = AgenteDoGabarito("openai", erradas={"Q05"})
    linhas = {"openai": rodar("openai", {"openai": ag}, ["openai"])}
    resumos = {"openai": agregar("openai", linhas["openai"], 30)}
    ex._escrever(resumos, linhas, _meta(precos))
    assert "| Só OpenAI | 29/30" in (tmp_path / "avaliacao.md").read_text(encoding="utf-8")
    (tmp_path / "acerto_manual.json").write_text(json.dumps({"openai:Q05": True}), encoding="utf-8")
    assert ex._so_relatorio() == 0
    md = (tmp_path / "avaliacao.md").read_text(encoding="utf-8")
    assert "| Só OpenAI | 30/30" in md and "Sobrescritas manuais de acerto (`dados/acerto_manual.json`): **1**" in md


def test_so_relatorio_sem_resultados_previos(tmp_path, monkeypatch):
    import src.avaliacao.executar as ex
    monkeypatch.setattr(ex, "SAIDA", tmp_path)
    assert ex._so_relatorio() == 2
