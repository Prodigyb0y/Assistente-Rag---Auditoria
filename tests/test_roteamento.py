"""Testes da regra de roteamento (src/orquestrador/politica.py). Tudo offline, sem custo."""
import pytest

from src.agentes.contrato import Citacao, ResultadoAgente, RespostaAuditoria
from src.custo import TabelaPrecos
from src.orquestrador.politica import (Falha, Motivo, Politica, classificar_falha, espera_backoff, melhor,
                                       motivo_escalonamento, ordem_por_preco, valida_ordem)


def resultado(*, confianca="alta", encontrado=True, citacoes=(("POL-ACE", "ACE-3"),), schema_ok=True,
              citacoes_ok=True, saida_bruta="{}", erro=None, excecao=None, provedor="anthropic"):
    resp = None
    if schema_ok:
        resp = RespostaAuditoria(resposta="x", encontrado=encontrado, confianca=confianca,
                                 citacoes=[Citacao(documento=d, secao=s) for d, s in citacoes])
    return ResultadoAgente(provedor=provedor, modelo="m", prompt_versao="v1", prompt_sha="s", pergunta_id="Q",
                           pergunta="p", resposta=resp, saida_bruta=saida_bruta if schema_ok or saida_bruta else "",
                           schema_ok=schema_ok, citacoes_ok=citacoes_ok, erro=erro, excecao=excecao)


# --- regra: aceitar ou escalar -----------------------------------------------------------

def test_aceita_resposta_valida_com_confianca_alta():
    assert motivo_escalonamento(resultado()) is None


def test_confianca_media_aceita_quando_minima_e_media():
    assert motivo_escalonamento(resultado(confianca="media"), "media") is None


def test_confianca_baixa_escala():
    assert motivo_escalonamento(resultado(confianca="baixa"), "media") is Motivo.CONFIANCA_BAIXA


def test_confianca_media_escala_quando_minima_e_alta():
    assert motivo_escalonamento(resultado(confianca="media"), "alta") is Motivo.CONFIANCA_BAIXA


def test_confianca_baixa_aceita_quando_minima_e_baixa():
    assert motivo_escalonamento(resultado(confianca="baixa"), "baixa") is None


def test_encontrado_false_sem_citacao_e_abstencao_e_escala_no_modo_original():
    r = resultado(encontrado=False, citacoes=(), confianca="alta")
    assert motivo_escalonamento(r) is Motivo.NAO_ENCONTRADO


def test_citacao_fora_dos_trechos_recuperados_escala():
    r = resultado(citacoes_ok=False, erro="citação fora dos trechos recuperados: POL-X/X-1")
    assert motivo_escalonamento(r) is Motivo.SEM_CITACAO_VALIDA


def test_encontrado_true_sem_citacao_escala():
    r = resultado(encontrado=True, citacoes=(), citacoes_ok=False, erro="encontrado=true sem nenhuma citação")
    assert motivo_escalonamento(r) is Motivo.SEM_CITACAO_VALIDA


def test_saida_fora_do_schema_escala():
    r = resultado(schema_ok=False, saida_bruta="texto livre", erro="saída não é JSON válido")
    assert motivo_escalonamento(r) is Motivo.SAIDA_INVALIDA


def test_sem_saida_nenhuma_e_erro():
    r = resultado(schema_ok=False, saida_bruta="", erro="resposta incompleta (limite de tokens de saída)")
    assert motivo_escalonamento(r) is Motivo.ERRO


def test_a_ordem_das_verificacoes_erro_vence_confianca():
    r = resultado(schema_ok=False, saida_bruta="", confianca="baixa", erro="x")
    assert motivo_escalonamento(r) is Motivo.ERRO


def test_abstencao_vence_confianca_baixa():
    r = resultado(encontrado=False, citacoes=(), confianca="baixa")
    assert motivo_escalonamento(r) is Motivo.NAO_ENCONTRADO


# --- classificação de falhas -------------------------------------------------------------

def _exc(nome, base=Exception, **attrs):
    e = type(nome, (base,), {})("falha")
    for k, v in attrs.items():
        setattr(e, k, v)
    return e


@pytest.mark.parametrize("exc", [
    _exc("APITimeoutError"), _exc("APIConnectionError"), TimeoutError(), ConnectionResetError(),
    _exc("RateLimitError", status_code=429), _exc("InternalServerError", status_code=500),
    _exc("APIStatusError", status_code=502), _exc("OverloadedError", status_code=529),
    _exc("APIStatusError", status_code=408), _exc("ConflictError", status_code=409),
])
def test_falhas_transitorias(exc):
    assert classificar_falha(exc) is Falha.TRANSITORIA


@pytest.mark.parametrize("exc", [
    _exc("BadRequestError", status_code=400), _exc("AuthenticationError", status_code=401),
    _exc("PermissionDeniedError", status_code=403), _exc("NotFoundError", status_code=404),
    _exc("UnprocessableEntityError", status_code=422), ValueError("bug"), KeyError("k"),
    _exc("RateLimitError", status_code=429, code="insufficient_quota"),
])
def test_falhas_definitivas(exc):
    assert classificar_falha(exc) is Falha.DEFINITIVA


def test_subclasse_de_timeout_conta_como_transitoria():
    base = type("APIConnectionError", (Exception,), {})
    sub = type("APITimeoutError", (base,), {})
    assert classificar_falha(sub("x")) is Falha.TRANSITORIA


# --- backoff -----------------------------------------------------------------------------

def test_backoff_exponencial_com_teto():
    esperas = [espera_backoff(n, 1.0, 8.0) for n in range(1, 7)]
    assert esperas == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_backoff_base_zero_nao_espera():
    assert espera_backoff(3, 0.0, 8.0) == 0.0


# --- escolha do melhor resultado, ordem por preço, validações ------------------------------

def test_melhor_prefere_aceitavel_a_invalido():
    ruim = resultado(schema_ok=False, saida_bruta="", erro="x", provedor="anthropic")
    bom = resultado(provedor="openai")
    assert melhor(ruim, bom) is bom and melhor(bom, ruim) is bom


def test_melhor_prefere_valido_a_invalido_mesmo_com_confianca_baixa():
    valido_baixa = resultado(confianca="baixa", provedor="anthropic")
    invalido = resultado(citacoes_ok=False, erro="x", confianca="alta", provedor="openai")
    assert melhor(invalido, valido_baixa) is valido_baixa


def test_melhor_empate_fica_com_o_primeiro():
    a = resultado(confianca="baixa", provedor="anthropic")
    b = resultado(confianca="baixa", provedor="openai")
    assert melhor(a, b) is a


def test_melhor_desempata_por_confianca():
    a = resultado(confianca="baixa", provedor="anthropic")
    b = resultado(confianca="media", provedor="openai")
    assert melhor(a, b, "alta") is b


def test_ordem_por_preco_comeca_pelo_mais_barato():
    tabela = TabelaPrecos.de_json("config/precos.json")
    modelos = {"openai": "gpt-6.1-terra", "anthropic": "claude-haiku-5-5"}
    ordem = ordem_por_preco(tabela, modelos)
    p = {k: tabela.get(m).input_mtok + tabela.get(m).output_mtok for k, m in modelos.items()}
    assert ordem[0] == min(p, key=p.get) and set(ordem) == {"openai", "anthropic"}


def test_ordem_acompanha_a_tabela_e_nao_um_nome_fixo():
    from src.custo import Preco
    tabela = TabelaPrecos({"a": Preco("a", "openai", 1.0, 5.0), "b": Preco("b", "anthropic", 3.0, 15.0)}, "t")
    assert ordem_por_preco(tabela, {"openai": "a", "anthropic": "b"}) == ("openai", "anthropic")
    assert ordem_por_preco(tabela, {"openai": "b", "anthropic": "a"}) == ("anthropic", "openai")


def test_valida_ordem():
    assert valida_ordem(["a", "b"], ["a", "b"]) == ("a", "b")
    for ruim in ([], ["a", "a"], ["a", "x"]):
        with pytest.raises(ValueError):
            valida_ordem(ruim, ["a", "b"])


def test_politica_valida_campos():
    with pytest.raises(ValueError):
        Politica(confianca_minima="altissima")
    with pytest.raises(ValueError):
        Politica(max_tentativas=0)
