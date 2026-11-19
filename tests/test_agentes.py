import json
from pathlib import Path

import pytest

from src.agentes.anthropic_agente import AgenteAnthropic
from src.agentes.contrato import MAX_PASSOS_FERRAMENTA
from src.agentes.ferramentas import FerramentaBusca
from src.agentes.openai_agente import AgenteOpenAI
from src.agentes.prompts import carregar_prompt
from src.config import carregar_settings
from src.custo import ControleCusto, OrcamentoExcedido, TabelaPrecos
from src.ingestao.chunker import carregar_documentos
from src.ingestao.indexador import carregar_indice, ingerir
from src.recuperacao.buscador import Buscador
from tests.fakes import (AnthropicRoteirizado, FakeEmbedder, OpenAIRoteirizado, anthropic_msg, openai_resp)

CONSULTA = "Acessos privilegiados são revisados a cada 90 dias pelo Dono do Sistema"
FINAL_OK = json.dumps({"resposta": "A cada 90 dias, pelo Dono do Sistema.", "encontrado": True,
                       "citacoes": [{"documento": "POL-ACE", "secao": "ACE-3"}], "confianca": "alta"})


@pytest.fixture
def ambiente(tmp_path):
    s = carregar_settings(env={}, usar_dotenv=False)
    tabela = TabelaPrecos.de_json("config/precos.json")
    tabela._precos["fake-bow"] = tabela.get("text-embedding-3-small")  # só para o cálculo de custo no teste
    controle = ControleCusto(tabela, s.orcamentos(), tmp_path / "c.jsonl")
    emb = FakeEmbedder()
    ingerir(carregar_documentos(Path("dados/documentos")), tmp_path / "idx", emb)
    buscador = Buscador(carregar_indice(tmp_path / "idx"), emb)
    return s, tabela, controle, buscador, carregar_prompt(diretorio=Path("prompts")), tmp_path


def _log(tmp_path):
    return [json.loads(l) for l in (tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()]


# --- ferramenta --------------------------------------------------------------------------

def test_ferramenta_devolve_trechos_e_registra_recuperados(ambiente):
    s, tabela, controle, buscador, prompt, _ = ambiente
    f = FerramentaBusca(buscador, tabela)
    saida = json.loads(f.executar(CONSULTA))
    assert len(saida["trechos"]) == 3 and set(saida["trechos"][0]) == {"documento", "secao", "titulo", "texto"}
    assert ("POL-ACE", "ACE-3") in f.recuperados
    assert f.tokens_embedding > 0 and f.custo_usd > 0 and f.consultas == [CONSULTA]


@pytest.mark.parametrize("entrada", [None, "", "   ", 42])
def test_ferramenta_rejeita_consulta_invalida(ambiente, entrada):
    _, tabela, _, buscador, _, _ = ambiente
    f = FerramentaBusca(buscador, tabela)
    assert "erro" in json.loads(f.executar(entrada))
    assert f.recuperados == set() and f.consultas == []


# --- agente OpenAI -----------------------------------------------------------------------

def _agente_openai(ambiente, respostas):
    s, tabela, controle, buscador, prompt, tmp = ambiente
    cli = OpenAIRoteirizado(respostas)
    return AgenteOpenAI(s, controle, buscador, tabela, prompt, client=cli), cli, tmp


def test_openai_fluxo_completo_com_tool_calling(ambiente):
    ag, cli, tmp = _agente_openai(ambiente, [
        openai_resp(id="r1", chamadas=[("call_1", {"consulta": CONSULTA})], tin=300, tout=40),
        openai_resp(id="r2", texto=FINAL_OK, tin=900, tout=60),
    ])
    r = ag.responder("Com que frequência os acessos privilegiados são revisados?", "Q01")
    assert r.valido and r.resposta.confianca == "alta" and r.n_chamadas_llm == 2
    assert (r.tokens_in, r.tokens_out) == (1200, 100)
    assert r.custo_llm_usd > 0 and r.custo_busca_usd > 0 and r.buscas == [CONSULTA]

    p1, p2 = cli.pedidos
    assert p1["text"]["format"]["type"] == "json_schema" and p1["text"]["format"]["strict"] is True
    assert p1["tools"][0]["name"] == "buscar_trechos" and "previous_response_id" not in p1
    assert p2["previous_response_id"] == "r1"
    assert p2["input"][0]["type"] == "function_call_output" and p2["input"][0]["call_id"] == "call_1"
    assert "ACE-3" in p2["input"][0]["output"]
    assert p2["instructions"] == p1["instructions"] and p2["tools"] == p1["tools"]  # reenviados
    assert not {"temperature", "top_p"} & set(p1)

    log = _log(tmp)
    llm = [x for x in log if x["provedor"] == "openai" and x["proposito"] == "agente"]
    assert [x["tokens_in"] for x in llm] == [300, 900] and all(x["tokens_out"] > 0 for x in llm)
    assert all(x["prompt_versao"] == "agente_resposta_v1" and x["pergunta_id"] == "Q01" for x in llm)


def test_openai_citacao_nao_recuperada_invalida(ambiente):
    inventada = json.dumps({"resposta": "x", "encontrado": True, "confianca": "alta",
                            "citacoes": [{"documento": "POL-FOR", "secao": "FOR-2"}]})
    ag, _, _ = _agente_openai(ambiente, [
        openai_resp(id="r1", chamadas=[("c", {"consulta": CONSULTA})]), openai_resp(id="r2", texto=inventada)])
    r = ag.responder("p", "Q")
    assert r.schema_ok and not r.citacoes_ok and not r.valido and "fora dos trechos" in r.erro


def test_openai_nao_chamar_ferramenta_e_citar_e_invalido(ambiente):
    ag, _, _ = _agente_openai(ambiente, [openai_resp(id="r1", texto=FINAL_OK)])
    r = ag.responder("p", "Q")
    assert not r.valido and r.buscas == []  # citou ACE-3 sem ter buscado


def test_openai_nao_encontrado_e_valido(ambiente):
    vazio = json.dumps({"resposta": "A base não traz isso.", "encontrado": False, "citacoes": [],
                        "confianca": "baixa"})
    ag, _, _ = _agente_openai(ambiente, [
        openai_resp(id="r1", chamadas=[("c", {"consulta": "algo inexistente"})]), openai_resp(id="r2", texto=vazio)])
    assert ag.responder("p", "Q").valido


def test_openai_saida_nao_json_e_resposta_incompleta(ambiente):
    ag, _, _ = _agente_openai(ambiente, [openai_resp(id="r1", texto="texto livre")])
    r = ag.responder("p", "Q")
    assert not r.schema_ok and "JSON" in r.erro
    ag2, _, _ = _agente_openai(ambiente, [openai_resp(id="r1", status="incomplete")])
    assert "incompleta" in ag2.responder("p", "Q").erro


def test_openai_limite_de_rodadas(ambiente):
    loop = [openai_resp(id=f"r{i}", chamadas=[(f"c{i}", {"consulta": CONSULTA})])
            for i in range(MAX_PASSOS_FERRAMENTA + 1)]
    ag, cli, _ = _agente_openai(ambiente, loop)
    r = ag.responder("p", "Q")
    assert "limite de rodadas" in r.erro and r.n_chamadas_llm == MAX_PASSOS_FERRAMENTA + 1


def test_openai_erro_da_api_vira_resultado_com_erro(ambiente):
    s, tabela, controle, buscador, prompt, tmp = ambiente

    class Quebrado:
        class responses:
            @staticmethod
            def create(**kw):
                raise TimeoutError("demorou")

    r = AgenteOpenAI(s, controle, buscador, tabela, prompt, client=Quebrado()).responder("p", "Q")
    assert "TimeoutError" in r.erro and not r.valido
    assert any(x["status"] == "erro" for x in _log(tmp))


def test_openai_teto_de_gasto_nao_chama_a_api(ambiente):
    s, tabela, _, buscador, prompt, tmp = ambiente
    s2 = carregar_settings(env={"BUDGET_OPENAI_USD": "0.000001"}, usar_dotenv=False)
    controle = ControleCusto(tabela, s2.orcamentos(), tmp / "c2.jsonl")
    cli = OpenAIRoteirizado([openai_resp(id="r1", texto=FINAL_OK)])
    with pytest.raises(OrcamentoExcedido):
        AgenteOpenAI(s2, controle, buscador, tabela, prompt, client=cli).responder("p", "Q")
    assert cli.pedidos == []


# --- agente Anthropic --------------------------------------------------------------------

def _agente_anthropic(ambiente, respostas):
    s, tabela, controle, buscador, prompt, tmp = ambiente
    cli = AnthropicRoteirizado(respostas)
    return AgenteAnthropic(s, controle, buscador, tabela, prompt, client=cli), cli, tmp


def test_anthropic_fluxo_completo_com_tool_use(ambiente):
    ag, cli, tmp = _agente_anthropic(ambiente, [
        anthropic_msg(stop_reason="tool_use", blocos=[("text", "vou buscar"), ("tool_use", "tu_1", {"consulta": CONSULTA})],
                      tin=400, tout=50),
        anthropic_msg(stop_reason="end_turn", blocos=[("text", FINAL_OK)], tin=1000, tout=70),
    ])
    r = ag.responder("Com que frequência os acessos privilegiados são revisados?", "Q01")
    assert r.valido and r.n_chamadas_llm == 2 and (r.tokens_in, r.tokens_out) == (1400, 120)

    p1, p2 = cli.pedidos
    assert p1["output_config"]["format"]["type"] == "json_schema"
    assert p1["tools"][0]["name"] == "buscar_trechos" and "input_schema" in p1["tools"][0]
    assert not {"temperature", "top_p", "top_k", "tool_choice"} & set(p1)
    # 2ª chamada: pergunta, conteúdo do assistente preservado e tool_result com o mesmo id
    assert [m["role"] for m in p2["messages"]] == ["user", "assistant", "user"]
    resultado = p2["messages"][2]["content"][0]
    assert resultado["type"] == "tool_result" and resultado["tool_use_id"] == "tu_1" and "ACE-3" in resultado["content"]

    llm = [x for x in _log(tmp) if x["provedor"] == "anthropic" and x["proposito"] == "agente"]
    assert [x["tokens_in"] for x in llm] == [400, 1000] and all(x["tokens_out"] > 0 for x in llm)
    assert all(x["prompt_versao"] == "agente_resposta_v1" for x in llm)


def test_anthropic_citacao_nao_recuperada_invalida(ambiente):
    inventada = json.dumps({"resposta": "x", "encontrado": True, "confianca": "media",
                            "citacoes": [{"documento": "POL-FOR", "secao": "FOR-2"}]})
    ag, _, _ = _agente_anthropic(ambiente, [
        anthropic_msg(stop_reason="tool_use", blocos=[("tool_use", "t", {"consulta": CONSULTA})]),
        anthropic_msg(stop_reason="end_turn", blocos=[("text", inventada)])])
    r = ag.responder("p", "Q")
    assert not r.valido and "fora dos trechos" in r.erro


def test_anthropic_max_tokens_e_erro(ambiente):
    ag, _, _ = _agente_anthropic(ambiente, [anthropic_msg(stop_reason="max_tokens", blocos=[("text", "{\"resp")])])
    r = ag.responder("p", "Q")
    assert "stop_reason=max_tokens" in r.erro and not r.valido


def test_anthropic_limite_de_rodadas(ambiente):
    loop = [anthropic_msg(stop_reason="tool_use", blocos=[("tool_use", f"t{i}", {"consulta": CONSULTA})])
            for i in range(MAX_PASSOS_FERRAMENTA + 1)]
    ag, _, _ = _agente_anthropic(ambiente, loop)
    assert "limite de rodadas" in ag.responder("p", "Q").erro


def test_anthropic_teto_de_gasto_nao_chama_a_api(ambiente):
    s, tabela, _, buscador, prompt, tmp = ambiente
    s2 = carregar_settings(env={"BUDGET_ANTHROPIC_USD": "0.000001"}, usar_dotenv=False)
    controle = ControleCusto(tabela, s2.orcamentos(), tmp / "c3.jsonl")
    cli = AnthropicRoteirizado([anthropic_msg(stop_reason="end_turn", blocos=[("text", FINAL_OK)])])
    with pytest.raises(OrcamentoExcedido):
        AgenteAnthropic(s2, controle, buscador, tabela, prompt, client=cli).responder("p", "Q")
    assert cli.pedidos == []


def test_mesmo_contrato_nos_dois_provedores(ambiente):
    ag_o, _, _ = _agente_openai(ambiente, [
        openai_resp(id="r1", chamadas=[("c", {"consulta": CONSULTA})]), openai_resp(id="r2", texto=FINAL_OK)])
    ag_a, _, _ = _agente_anthropic(ambiente, [
        anthropic_msg(stop_reason="tool_use", blocos=[("tool_use", "t", {"consulta": CONSULTA})]),
        anthropic_msg(stop_reason="end_turn", blocos=[("text", FINAL_OK)])])
    ro, ra = ag_o.responder("p", "Q"), ag_a.responder("p", "Q")
    assert ro.para_dict().keys() == ra.para_dict().keys()
    assert ro.resposta == ra.resposta and ro.prompt_versao == ra.prompt_versao
