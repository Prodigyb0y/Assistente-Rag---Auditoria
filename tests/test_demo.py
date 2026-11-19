"""Testes do núcleo da demo (limites, cache, serviço). Offline, sem custo."""
import json
import threading
from pathlib import Path

import pytest

from src.interface.cache import CacheRespostas, chave_cache
from src.interface.limites import LimiteDiario, id_visitante
from src.interface.servico import RespostaDemo, ServicoDemo, validar_pergunta
from src.orquestrador.orquestrador import Orquestrador
from src.orquestrador.politica import Politica
from tests.test_avaliacao import PERGUNTAS, AgenteDoGabarito
from tests.test_orquestrador import AgenteFalso, falhou, ok
from tests.test_roteamento import _exc

Q1 = PERGUNTAS[0]["pergunta"]
Q2 = PERGUNTAS[1]["pergunta"]


# --- limites -----------------------------------------------------------------------------

def test_limite_por_visitante():
    lim = LimiteDiario(None, por_visitante=2, global_dia=100, teto_custo_usd=1.0)
    assert lim.reservar("a").permitido and lim.reservar("a").permitido
    d = lim.reservar("a")
    assert not d.permitido and d.motivo == "limite_visitante" and d.restantes_visitante == 0
    assert lim.reservar("b").permitido   # outro visitante não é afetado


def test_limite_global():
    lim = LimiteDiario(None, por_visitante=10, global_dia=2, teto_custo_usd=1.0)
    assert lim.reservar("a").permitido and lim.reservar("b").permitido
    assert lim.reservar("c").motivo == "limite_global"


def test_teto_de_custo_diario_bloqueia_depois_de_atingido():
    lim = LimiteDiario(None, 10, 100, teto_custo_usd=0.01)
    assert lim.reservar("a").permitido
    lim.registrar_custo(0.012)
    assert lim.reservar("a").motivo == "teto_custo"


def test_virada_do_dia_zera_contadores():
    dia = {"d": "2026-11-19"}
    lim = LimiteDiario(None, 1, 1, 1.0, hoje=lambda: dia["d"])
    assert lim.reservar("a").permitido and not lim.reservar("a").permitido
    lim.registrar_custo(0.5)
    dia["d"] = "2026-11-20"
    assert lim.reservar("a").permitido and lim.custo_hoje_usd == 0.0


def test_estado_persiste_entre_instancias_no_mesmo_dia(tmp_path):
    f = tmp_path / "estado.json"
    a = LimiteDiario(f, 1, 10, 1.0, hoje=lambda: "2026-11-19")
    assert a.reservar("a").permitido
    b = LimiteDiario(f, 1, 10, 1.0, hoje=lambda: "2026-11-19")
    assert b.reservar("a").motivo == "limite_visitante"
    c = LimiteDiario(f, 1, 10, 1.0, hoje=lambda: "2026-11-20")   # outro dia: recomeça
    assert c.reservar("a").permitido


def test_arquivo_de_estado_corrompido_nao_derruba(tmp_path):
    f = tmp_path / "estado.json"
    f.write_text("{lixo", encoding="utf-8")
    assert LimiteDiario(f, 1, 1, 1.0).reservar("a").permitido


def test_estornar_devolve_a_pergunta():
    lim = LimiteDiario(None, 1, 1, 1.0)
    lim.reservar("a")
    lim.estornar("a")
    assert lim.reservar("a").permitido


def test_reservas_simultaneas_respeitam_o_limite_global():
    lim = LimiteDiario(None, por_visitante=1000, global_dia=10, teto_custo_usd=1.0)
    permitidos = []
    def tenta(i):
        permitidos.append(lim.reservar(f"v{i}").permitido)
    ts = [threading.Thread(target=tenta, args=(i,)) for i in range(60)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(permitidos) == 10


def test_id_visitante_nao_expoe_o_ip_e_depende_do_sal(tmp_path):
    v = id_visitante("200.10.20.30", "sal1")
    assert "200.10.20.30" not in v and len(v) == 16
    assert v == id_visitante("200.10.20.30", "sal1") and v != id_visitante("200.10.20.30", "sal2")
    lim = LimiteDiario(tmp_path / "e.json", 5, 5, 1.0)
    lim.reservar(v)
    assert "200.10.20.30" not in (tmp_path / "e.json").read_text(encoding="utf-8")


# --- cache -------------------------------------------------------------------------------

def test_chave_normaliza_caixa_acento_espaco_e_pontuacao_final():
    a = chave_cache("Qual o prazo de revogação?", "v1", "m")
    assert a == chave_cache("  qual o PRAZO   de revogacao ", "v1", "m")
    assert a != chave_cache("Qual o prazo de revogação?", "v2", "m")      # outro prompt
    assert a != chave_cache("Qual o prazo de revogação?", "v1", "outro")  # outros modelos


def test_cache_persiste_e_descarta_a_mais_antiga(tmp_path):
    f = tmp_path / "c.json"
    c = CacheRespostas(f, max_itens=2)
    c.guardar("a", {"x": 1}); c.guardar("b", {"x": 2}); c.guardar("c", {"x": 3})
    assert c.obter("a") is None and c.obter("c") == {"x": 3} and len(c) == 2
    assert CacheRespostas(f).obter("b") == {"x": 2}


# --- validação ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [None, "", "   ", "\x00\x01", "x" * 301])
def test_perguntas_invalidas(texto):
    assert validar_pergunta(texto, 300) is None


def test_pergunta_valida_e_limpa():
    assert validar_pergunta("  Qual\x00 o   prazo?\n", 300) == "Qual o prazo?"


# --- serviço -----------------------------------------------------------------------------

def servico(tmp_path, agentes, ordem, por_visitante=3, global_dia=50, teto=1.0, cache=True):
    orq = Orquestrador(agentes, ordem, Politica(), dormir=lambda s: None)
    lim = LimiteDiario(None, por_visitante, global_dia, teto)
    c = CacheRespostas(tmp_path / "c.json" if cache else None)
    return ServicoDemo(orq, lim, c, prompt_versao="v1", modelos="m1+m2"), lim


class Contador(AgenteDoGabarito):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.chamadas = 0

    def responder(self, pergunta, pergunta_id=""):
        self.chamadas += 1
        return super().responder(pergunta, pergunta_id)


def test_pergunta_valida_responde_com_citacao_provedor_e_custo(tmp_path):
    ag = Contador("anthropic", custo=0.0005)
    s, lim = servico(tmp_path, {"anthropic": ag}, ["anthropic"])
    r = s.perguntar(Q1, "v")
    assert r.status == "ok" and r.ok and r.provedor == "anthropic" and r.aceita_pela_regra
    assert r.citacoes == [{"documento": PERGUNTAS[0]["documento"], "secao": PERGUNTAS[0]["secao"]}]
    assert r.custo_usd == pytest.approx(0.0005) and r.restantes_visitante == 2
    assert lim.custo_hoje_usd == pytest.approx(0.0005)


def test_pergunta_repetida_vem_do_cache_sem_gastar_limite_nem_api(tmp_path):
    ag = Contador("anthropic")
    s, lim = servico(tmp_path, {"anthropic": ag}, ["anthropic"], por_visitante=1)
    s.perguntar(Q1, "v")
    r2 = s.perguntar(Q1.upper() + "  ", "v")      # mesma pergunta, escrita diferente
    assert r2.status == "cache" and r2.ok and r2.custo_usd == 0.0 and ag.chamadas == 1
    assert r2.restantes_visitante == 0 and r2.resposta
    assert lim.custo_hoje_usd == pytest.approx(0.001)   # só a 1a chamada custou


def test_cache_hit_funciona_mesmo_com_limite_esgotado(tmp_path):
    s, _ = servico(tmp_path, {"anthropic": Contador("anthropic")}, ["anthropic"], por_visitante=1)
    s.perguntar(Q1, "v")
    assert s.perguntar(Q2, "v").status == "limite_visitante"
    assert s.perguntar(Q1, "v").status == "cache"


def test_limite_do_visitante_mostra_mensagem_e_nao_chama_api(tmp_path):
    ag = Contador("anthropic")
    s, _ = servico(tmp_path, {"anthropic": ag}, ["anthropic"], por_visitante=1)
    s.perguntar(Q1, "v")
    r = s.perguntar(Q2, "v")
    assert r.status == "limite_visitante" and not r.ok and "limite" in r.mensagem and ag.chamadas == 1


def test_limite_global_e_teto_de_custo(tmp_path):
    ag = Contador("anthropic", custo=0.6)
    s, _ = servico(tmp_path, {"anthropic": ag}, ["anthropic"], global_dia=1)
    s.perguntar(Q1, "a")
    assert s.perguntar(Q2, "b").status == "limite_global"
    ag2 = Contador("anthropic", custo=0.6)
    s2, _ = servico(tmp_path, {"anthropic": ag2}, ["anthropic"], teto=0.5, cache=False)
    s2.perguntar(Q1, "a")                                   # gasta 0.6, acima do teto de 0.5
    assert s2.perguntar(Q2, "b").status == "teto_custo" and ag2.chamadas == 1


@pytest.mark.parametrize("texto", ["", None, "x" * 400])
def test_entrada_invalida_nao_gasta_nada(tmp_path, texto):
    ag = Contador("anthropic")
    s, lim = servico(tmp_path, {"anthropic": ag}, ["anthropic"])
    r = s.perguntar(texto, "v")
    assert r.status == "invalida" and ag.chamadas == 0 and lim.reservar("v").restantes_visitante == 2


def test_falha_dos_provedores_devolve_a_pergunta(tmp_path):
    t = _exc("APITimeoutError")
    ag = AgenteFalso("anthropic", [falhou("anthropic", t)] * 3)
    s, lim = servico(tmp_path, {"anthropic": ag}, ["anthropic"], por_visitante=1)
    r = s.perguntar(Q1, "v")
    assert r.status == "falha" and "não foi descontada" in r.mensagem
    assert lim.consultar("v").restantes_visitante == 1


def test_so_resposta_aceita_vai_para_o_cache(tmp_path):
    fraco = Contador("anthropic", confianca="baixa")
    s, _ = servico(tmp_path, {"anthropic": fraco}, ["anthropic"])
    r = s.perguntar(Q1, "v")
    assert r.ok and not r.aceita_pela_regra       # melhor esforço: mostrada, mas não guardada
    assert s.perguntar(Q1, "v").status == "ok" and fraco.chamadas == 2


def test_orquestrado_na_demo_escala_e_cobra_os_dois(tmp_path):
    barato, caro = Contador("anthropic", custo=0.0005, confianca="baixa"), Contador("openai", custo=0.002)
    s, lim = servico(tmp_path, {"anthropic": barato, "openai": caro}, ["anthropic", "openai"])
    r = s.perguntar(Q1, "v")
    assert r.provedor == "openai" and r.custo_usd == pytest.approx(0.0025)
    assert lim.custo_hoje_usd == pytest.approx(0.0025)


def test_custo_de_tentativas_perdidas_conta_no_teto(tmp_path):
    perdida = falhou("anthropic", _exc("AuthenticationError", status_code=401))
    perdida.custo_llm_usd = 0.3
    s, lim = servico(tmp_path, {"anthropic": AgenteFalso("anthropic", [perdida])}, ["anthropic"])
    assert s.perguntar(Q1, "v").status == "falha" and lim.custo_hoje_usd == pytest.approx(0.3)


# --- configuração, texto da tela e criação do índice ---------------------------------------

def test_config_demo_defaults_e_env():
    from src.interface.config_demo import carregar_config_demo
    c = carregar_config_demo({})
    assert (c.por_visitante_dia, c.global_dia, c.teto_custo_dia_usd, c.max_chars) == (5, 60, 0.25, 300)
    assert c.sal_padrao
    c2 = carregar_config_demo({"DEMO_POR_VISITANTE_DIA": "2", "DEMO_SALT": "segredo-xyz"})
    assert c2.por_visitante_dia == 2 and not c2.sal_padrao
    assert "segredo-xyz" not in repr(c2)


def test_config_demo_invalida_nao_vaza_valor():
    from src.config import ConfigError
    from src.interface.config_demo import carregar_config_demo
    with pytest.raises(ConfigError) as e:
        carregar_config_demo({"DEMO_GLOBAL_DIA": "0", "DEMO_SALT": "segredo-xyz"})
    assert "global_dia" in str(e.value) and "segredo-xyz" not in str(e.value)


def test_extrair_ip_usa_a_ultima_entrada_do_proxy():
    from src.interface.limites import extrair_ip
    assert extrair_ip({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "127.0.0.1") == "10.0.0.1"
    assert extrair_ip({}, "127.0.0.1") == "127.0.0.1" and extrair_ip(None, None) == "desconhecido"


def test_formatar_resposta_com_fonte_e_detalhes(tmp_path):
    from src.interface.formatar import formatar
    s, _ = servico(tmp_path, {"anthropic": Contador("anthropic", custo=0.0005)}, ["anthropic"])
    texto, det = formatar(s.perguntar(Q1, "v"))
    assert PERGUNTAS[0]["resposta_esperada"] in texto and "Fontes citadas" in texto and "POL-ACE / ACE-3" in texto
    assert "provedor: anthropic" in det and "0.000500" in det and "restantes" in det
    texto2, det2 = formatar(s.perguntar(Q1, "v"))
    assert "cache" in det2


def test_formatar_bloqueio_e_nao_encontrado():
    from src.interface.formatar import formatar
    t, d = formatar(RespostaDemo(status="limite_visitante", mensagem="limite hoje", restantes_visitante=0))
    assert "limite hoje" in t and "0" in d
    t2, _ = formatar(RespostaDemo(status="ok", resposta="Não consta.", encontrado=False, confianca="baixa",
                                  aceita_pela_regra=False))
    assert "não traz essa informação" in t2 and "nenhuma" in t2 and "melhor resposta" in t2


def test_garantir_indice_cria_uma_vez_e_depois_nao_chama_api(tmp_path):
    from src.interface.montagem import garantir_indice
    from tests.fakes import FakeEmbedder
    emb = FakeEmbedder()
    assert garantir_indice(tmp_path / "idx", Path("dados/documentos"), emb) == "criado" and emb.chamadas == 1
    assert garantir_indice(tmp_path / "idx", Path("dados/documentos"), emb) == "existente" and emb.chamadas == 1


def test_servico_restantes_nao_reserva(tmp_path):
    s, lim = servico(tmp_path, {"anthropic": AgenteDoGabarito("anthropic")}, ["anthropic"], por_visitante=3)
    assert s.restantes("v") == 3 and s.restantes("v") == 3
    s.perguntar(Q1, "v")
    assert s.restantes("v") == 2
