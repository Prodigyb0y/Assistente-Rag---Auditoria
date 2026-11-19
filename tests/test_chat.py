"""Testes da lógica do chat (sem Gradio)."""
from __future__ import annotations

import pytest

from src.interface import chat
from src.interface.servico import RespostaDemo

PERGUNTAS = chat.carregar_perguntas()


def _ok(**kw):
    base = dict(status="ok", resposta="A cada 90 dias.", encontrado=True, confianca="alta",
                citacoes=[{"documento": "POL-ACE", "secao": "ACE-3"}], provedor="anthropic",
                aceita_pela_regra=True, custo_usd=0.000467, latencia_s=5.3, restantes_visitante=4)
    base.update(kw)
    return RespostaDemo(**base)


# --- documentos e trechos ---------------------------------------------------------------

def test_arquivo_do_documento_valido_e_invalido():
    assert chat.arquivo_do_documento("POL-ACE").name.startswith("POL-ACE_")
    for ruim in (None, "", "POL-ZZZ", "../POL-ACE", "POL-ACE/../../x", "pol-ace", "POL-ACE*"):
        assert chat.arquivo_do_documento(ruim) is None


def test_carregar_secao_traz_titulo_e_texto_e_limita_tamanho(tmp_path):
    titulo, texto = chat.carregar_secao("POL-ACE", "ACE-3")
    assert titulo == "Revisão periódica" and "90 dias" in texto and "\n" not in texto
    (tmp_path / "POL-XXX_longo.md").write_text("## XXX-1 Longo\n\n" + "palavra " * 400 + "\n## XXX-2 Outro\nx\n",
                                               encoding="utf-8")
    _, longo = chat.carregar_secao("POL-XXX", "XXX-1", tmp_path)
    assert len(longo) <= chat.MAX_TRECHO + 1 and longo.endswith("…")


@pytest.mark.parametrize("doc,sec", [("POL-ACE", "ACE-99"), ("POL-ACE", "../x"), ("POL-ACE", ""), ("POL-ZZZ", "ZZZ-1")])
def test_carregar_secao_inexistente_ou_invalida(doc, sec):
    assert chat.carregar_secao(doc, sec) is None


def test_toda_fonte_do_gabarito_resolve_para_um_trecho():
    for q in PERGUNTAS:
        achada = chat.carregar_secao(q["documento"], q["secao"])
        assert achada is not None and achada[1], q["id"]


def test_documentos_citados_sem_repetir_e_ignorando_invalidos():
    cit = [{"documento": "POL-ACE", "secao": "ACE-3"}, {"documento": "POL-ACE", "secao": "ACE-4"},
           {"documento": "POL-INC", "secao": "INC-5"}, {"documento": "../x", "secao": "X-1"}]
    nomes = [p.name.split("_")[0] for p in chat.documentos_citados(cit)]
    assert nomes == ["POL-ACE", "POL-INC"]


# --- mensagens --------------------------------------------------------------------------

def test_mensagem_com_resposta_fonte_trecho_e_rodape():
    m = chat.montar_mensagem(_ok())
    assert m.startswith("A cada 90 dias.")
    assert "> **POL-ACE · ACE-3** — Revisão periódica" in m and "90 dias pelo Dono do Sistema" in m
    assert "Confiança: alta" in m and "anthropic" in m and "US$ 0.000467" in m


def test_mensagem_de_cache_nao_mostra_custo():
    m = chat.montar_mensagem(_ok(status="cache"))
    assert "cache (sem custo)" in m and "US$" not in m


def test_mensagem_nao_encontrado_e_sem_fonte_e_regra_nao_aceita():
    m = chat.montar_mensagem(_ok(encontrado=False, citacoes=[], aceita_pela_regra=False, confianca="baixa"))
    assert "não traz essa informação" in m and "Nenhuma fonte citada" in m and "melhor resposta obtida" in m


def test_mensagem_de_nao_encontrado_confirmado_nao_diz_que_a_regra_falhou():
    m = chat.montar_mensagem(_ok(encontrado=False, citacoes=[], aceita_pela_regra=True, confianca="baixa",
                                 status_orq="nao_encontrado_confirmado"))
    assert "Os dois provedores confirmaram" in m and "melhor resposta obtida" not in m


def test_mensagem_de_divergencia_pede_conferencia_no_documento():
    m = chat.montar_mensagem(_ok(aceita_pela_regra=False, status_orq="divergencia"))
    assert "divergiram" in m and "melhor resposta obtida" not in m


def test_mensagem_de_consenso_informa_a_confirmacao():
    m = chat.montar_mensagem(_ok(status_orq="aceita_por_consenso"))
    assert "Confirmada por dois provedores" in m


def test_mensagem_de_bloqueio():
    m = chat.montar_mensagem(RespostaDemo(status="limite_visitante", mensagem="limite hoje"))
    assert m == "⚠️ **limite hoje**"


def test_mensagem_limita_a_quantidade_de_fontes():
    cit = [{"documento": "POL-ACE", "secao": f"ACE-{i}"} for i in range(1, 6)]
    m = chat.montar_mensagem(_ok(citacoes=cit))
    assert m.count("> **POL-ACE ·") == chat.MAX_FONTES and "+2 fonte(s) não exibida(s)" in m


# --- sugestões --------------------------------------------------------------------------

def test_sugestoes_iniciais_uma_por_documento():
    s = chat.sugestoes_iniciais(PERGUNTAS, 6)
    docs = [next(q["documento"] for q in PERGUNTAS if q["pergunta"] == t) for t in s]
    assert len(s) == 6 and len(set(docs)) == 6


def test_sugestoes_seguimento_priorizam_o_mesmo_documento_e_nao_repetem():
    feitas = [PERGUNTAS[0]["pergunta"].upper() + "?"]   # normalização: caixa e pontuação
    s = chat.sugestoes_seguimento(PERGUNTAS, {"POL-ACE"}, feitas, 3)
    por_doc = {q["pergunta"]: q["documento"] for q in PERGUNTAS}
    assert len(s) == 3 and PERGUNTAS[0]["pergunta"] not in s
    assert por_doc[s[0]] == "POL-ACE"
    assert len(set(s)) == 3


def test_sugestoes_seguimento_sem_pendentes():
    todas = [q["pergunta"] for q in PERGUNTAS]
    assert chat.sugestoes_seguimento(PERGUNTAS, {"POL-ACE"}, todas) == []


# --- turno ------------------------------------------------------------------------------

def test_iniciar_turno_mostra_pergunta_e_espera():
    h = chat.iniciar_turno([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}], "c")
    assert h[-2:] == [{"role": "user", "content": "c"}, {"role": "assistant", "content": chat.ESPERA}] and len(h) == 4


class _Servico:
    def __init__(self, r):
        self.r = r

    def perguntar(self, texto, visitante):
        return self.r


def _turno(r, hist=None):
    return chat.concluir_turno(_Servico(r), "Quanto?", "v", hist, PERGUNTAS, por_visitante=5)


def test_turno_ok_traz_sugestoes_arquivo_e_status():
    t = _turno(_ok())
    assert t.historico[-1]["role"] == "assistant" and len(t.sugestoes) == 3
    assert len(t.arquivos) == 1 and t.arquivos[0].endswith(".md")
    assert t.status == "Perguntas restantes hoje: **4** de 5"


def test_turno_bloqueado_nao_sugere_nem_oferece_arquivo():
    t = _turno(RespostaDemo(status="limite_visitante", mensagem="limite", restantes_visitante=0))
    assert t.sugestoes == [] and t.arquivos == [] and "**0** de 5" in t.status


def test_turno_com_pergunta_invalida_volta_as_sugestoes_iniciais():
    t = _turno(RespostaDemo(status="invalida", mensagem="escreva", restantes_visitante=3))
    assert t.sugestoes == chat.sugestoes_iniciais(PERGUNTAS, 6) and t.arquivos == []


def test_turno_nao_sugere_o_que_ja_foi_perguntado():
    feita = PERGUNTAS[0]["pergunta"]
    t = _turno(_ok(), [{"role": "user", "content": feita}, {"role": "assistant", "content": "x"}])
    assert feita not in t.sugestoes
