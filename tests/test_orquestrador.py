"""Testes do orquestrador com agentes falsos e relógio falso: sem rede, sem custo, sem espera real."""
import json
from pathlib import Path

import pytest

from src.agentes.contrato import ResultadoAgente
from src.custo import OrcamentoExcedido
from src.orquestrador.orquestrador import (ACEITA_APOS_ESCALONAMENTO, ACEITA_NO_PRIMEIRO, FALHA, MELHOR_ESFORCO,
                                           LogRoteamento, Orquestrador)
from src.orquestrador.politica import Politica
from tests.test_roteamento import _exc, resultado


class AgenteFalso:
    """Devolve, em ordem, os itens do roteiro: ResultadoAgente ou exceção (que é levantada)."""

    def __init__(self, provedor, roteiro):
        self.provedor, self.modelo = provedor, f"modelo-{provedor}"
        self.roteiro = list(roteiro)
        self.chamadas = 0

    def responder(self, pergunta, pergunta_id=""):
        self.chamadas += 1
        item = self.roteiro.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class Relogio:
    def __init__(self):
        self.t = 0.0
        self.esperas: list[float] = []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.esperas.append(s)
        self.t += s


def ok(prov, **kw):
    r = resultado(provedor=prov, **kw)
    r.tokens_in, r.tokens_out, r.custo_llm_usd, r.latencia_s = 100, 20, 0.001, 1.0
    return r


def falhou(prov, exc):
    r = resultado(provedor=prov, schema_ok=False, saida_bruta="", erro=f"{type(exc).__name__}: x", excecao=exc)
    r.tokens_in, r.tokens_out, r.custo_llm_usd = 0, 0, 0.0
    return r


def montar(tmp_path, barato, caro, **pol):
    rel = Relogio()
    ags = {"anthropic": barato, "openai": caro}
    log = LogRoteamento(tmp_path / "roteamento.jsonl")
    orq = Orquestrador(ags, ["anthropic", "openai"], Politica(**pol), log, dormir=rel.dormir, relogio=rel.agora)
    return orq, rel, tmp_path / "roteamento.jsonl"


def ler(caminho: Path):
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines()]


# --- caminho feliz e escalonamento -------------------------------------------------------

def test_aceita_no_primeiro_sem_chamar_o_segundo(tmp_path):
    b, c = AgenteFalso("anthropic", [ok("anthropic")]), AgenteFalso("openai", [])
    orq, rel, log = montar(tmp_path, b, c)
    res = orq.responder("p", "Q01")
    assert res.status == ACEITA_NO_PRIMEIRO and res.provedor_final == "anthropic" and not res.escalou
    assert c.chamadas == 0 and rel.esperas == [] and res.motivo_escalonamento is None
    assert [e["evento"] for e in ler(log)] == ["tentativa", "decisao", "final"]


def test_confianca_baixa_escala_para_o_segundo(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai", confianca="alta")])
    orq, _, log = montar(tmp_path, b, c)
    res = orq.responder("p", "Q01")
    assert res.status == ACEITA_APOS_ESCALONAMENTO and res.provedor_final == "openai" and res.escalou
    assert res.rota == ["anthropic", "openai"] and res.motivo_escalonamento == "confianca_baixa"
    dec = [e for e in ler(log) if e["evento"] == "decisao"]
    assert dec[0]["acao"] == "escalar" and dec[0]["para"] == "openai" and dec[0]["motivo"] == "confianca_baixa"
    assert dec[1]["acao"] == "aceitar"


def test_sem_citacao_valida_escala(tmp_path):
    sem = ok("anthropic", encontrado=False, citacoes=())
    b, c = AgenteFalso("anthropic", [sem]), AgenteFalso("openai", [ok("openai")])
    orq, _, _ = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert res.motivo_escalonamento == "sem_citacao_valida" and res.provedor_final == "openai"


def test_politica_com_confianca_minima_alta_escala_media(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic", confianca="media")])
    c = AgenteFalso("openai", [ok("openai")])
    orq, _, _ = montar(tmp_path, b, c, confianca_minima="alta")
    assert orq.responder("p").provedor_final == "openai"


# --- retry com backoff ---------------------------------------------------------------------

def test_retry_em_falha_transitoria_ate_dar_certo(tmp_path):
    t = _exc("APITimeoutError")
    b = AgenteFalso("anthropic", [falhou("anthropic", t), falhou("anthropic", t), ok("anthropic")])
    c = AgenteFalso("openai", [])
    orq, rel, log = montar(tmp_path, b, c)
    res = orq.responder("p", "Q01")
    assert b.chamadas == 3 and c.chamadas == 0 and rel.esperas == [1.0, 2.0]
    assert res.status == ACEITA_NO_PRIMEIRO and len(res.tentativas) == 3
    eventos = [e["evento"] for e in ler(log)]
    assert eventos.count("retry") == 2 and eventos.count("tentativa") == 3


def test_retries_esgotados_vai_para_o_fallback_sem_esperar_depois_da_ultima(tmp_path):
    t = _exc("RateLimitError", status_code=429)
    b = AgenteFalso("anthropic", [falhou("anthropic", t)] * 3)
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, log = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert b.chamadas == 3 and rel.esperas == [1.0, 2.0]  # 2 esperas, nenhuma depois da 3a falha
    assert res.status == ACEITA_APOS_ESCALONAMENTO and res.provedor_final == "openai"
    assert res.motivo_escalonamento == "erro"
    assert "retries_esgotados" in [e["evento"] for e in ler(log)]


def test_espera_respeita_o_teto(tmp_path):
    t = _exc("APIConnectionError")
    b = AgenteFalso("anthropic", [falhou("anthropic", t)] * 5)
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, _ = montar(tmp_path, b, c, max_tentativas=5, espera_base_s=1.0, espera_max_s=3.0)
    orq.responder("p")
    assert rel.esperas == [1.0, 2.0, 3.0, 3.0]


def test_falha_definitiva_nao_repete_e_vai_direto_ao_fallback(tmp_path):
    auth = _exc("AuthenticationError", status_code=401)
    b = AgenteFalso("anthropic", [falhou("anthropic", auth)])
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, _ = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert b.chamadas == 1 and rel.esperas == [] and res.provedor_final == "openai"


def test_erro_sem_excecao_nao_repete(tmp_path):
    """Ex.: limite de rodadas de ferramenta ou resposta incompleta: repetir não ajuda."""
    sem_exc = resultado(schema_ok=False, saida_bruta="", erro="limite de rodadas de ferramenta excedido")
    b = AgenteFalso("anthropic", [sem_exc])
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, _ = montar(tmp_path, b, c)
    assert orq.responder("p").provedor_final == "openai" and b.chamadas == 1 and rel.esperas == []


def test_excecao_inesperada_do_agente_vira_falha_definitiva(tmp_path):
    b = AgenteFalso("anthropic", [ValueError("bug")])
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, _ = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert res.provedor_final == "openai" and rel.esperas == [] and b.chamadas == 1


# --- teto de gasto -------------------------------------------------------------------------

def test_orcamento_excedido_no_primeiro_pula_sem_retry(tmp_path):
    b = AgenteFalso("anthropic", [OrcamentoExcedido("teto")])
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, log = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert b.chamadas == 1 and rel.esperas == [] and res.provedor_final == "openai"
    assert res.motivo_escalonamento == "orcamento_excedido" and res.rota == ["openai"]
    assert res.status == ACEITA_APOS_ESCALONAMENTO
    ev = [e["evento"] for e in ler(log)]
    assert "orcamento_bloqueado" in ev


def test_orcamento_excedido_nos_dois_devolve_falha(tmp_path):
    b = AgenteFalso("anthropic", [OrcamentoExcedido("teto")])
    c = AgenteFalso("openai", [OrcamentoExcedido("teto")])
    orq, _, log = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert res.status == FALHA and res.final is None and res.provedor_final is None and res.rota == []
    assert ler(log)[-1]["status"] == FALHA


# --- ninguém passa na regra ----------------------------------------------------------------

def test_nenhum_aceito_devolve_o_melhor_esforco(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai", encontrado=False, citacoes=(), confianca="alta")])
    orq, _, _ = montar(tmp_path, b, c)
    res = orq.responder("p")
    # Nenhum passa na regra; ambos são 'válidos'. Desempata a confiança: openai (alta) > anthropic (baixa).
    assert res.status == MELHOR_ESFORCO and res.provedor_final == "openai" and res.escalou


def test_nenhum_aceito_empate_fica_com_o_primeiro(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai", confianca="baixa")])
    orq, _, _ = montar(tmp_path, b, c)
    assert orq.responder("p").provedor_final == "anthropic"


def test_primeiro_aceitavel_depois_de_falha_do_segundo_nao_acontece(tmp_path):
    """Se o primeiro é aceito, o segundo nunca é consultado, mesmo que estivesse quebrado."""
    b = AgenteFalso("anthropic", [ok("anthropic")])
    c = AgenteFalso("openai", [OrcamentoExcedido("x")])
    orq, _, _ = montar(tmp_path, b, c)
    assert orq.responder("p").status == ACEITA_NO_PRIMEIRO and c.chamadas == 0


# --- prazo total ---------------------------------------------------------------------------

def test_prazo_total_impede_novo_retry(tmp_path):
    t = _exc("APITimeoutError")
    b = AgenteFalso("anthropic", [falhou("anthropic", t)] * 3)
    c = AgenteFalso("openai", [ok("openai")])
    orq, rel, log = montar(tmp_path, b, c, prazo_total_s=1.5)   # a 1a espera (1s) cabe; a 2a (2s) não
    res = orq.responder("p")
    assert b.chamadas == 2 and rel.esperas == [1.0]
    assert "prazo_excedido" in [e["evento"] for e in ler(log)]
    assert res.provedor_final == "openai"


def test_prazo_total_impede_consultar_o_segundo(tmp_path):
    rel = Relogio()

    class Lento(AgenteFalso):
        def responder(self, *a, **k):
            rel.t += 200.0   # simula uma resposta de 200 s
            return super().responder(*a, **k)

    b = Lento("anthropic", [ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai")])
    orq = Orquestrador({"anthropic": b, "openai": c}, ["anthropic", "openai"], Politica(prazo_total_s=120),
                       LogRoteamento(tmp_path / "r.jsonl"), dormir=rel.dormir, relogio=rel.agora)
    res = orq.responder("p")
    assert c.chamadas == 0 and res.status == MELHOR_ESFORCO and res.provedor_final == "anthropic"


# --- contabilidade e log -------------------------------------------------------------------

def test_custo_e_tokens_somam_todas_as_tentativas(tmp_path):
    t = _exc("APITimeoutError")
    perdida = falhou("anthropic", t)
    perdida.tokens_in, perdida.tokens_out, perdida.custo_llm_usd = 50, 5, 0.0005  # 1a chamada cobrada
    b = AgenteFalso("anthropic", [perdida, ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai")])
    orq, _, _ = montar(tmp_path, b, c)
    res = orq.responder("p")
    assert len(res.tentativas) == 3
    assert res.tokens_in == 50 + 100 + 100 and res.tokens_out == 5 + 20 + 20
    assert res.custo_total_usd == pytest.approx(0.0005 + 0.001 + 0.001)


def test_log_registra_versao_do_prompt_tokens_e_nao_vaza_mensagem_de_erro(tmp_path):
    e = _exc("AuthenticationError", status_code=401)
    e.args = ("Incorrect API key provided: sk-proj-SEGREDO",)
    b = AgenteFalso("anthropic", [falhou("anthropic", e)])
    c = AgenteFalso("openai", [ok("openai")])
    orq, _, log = montar(tmp_path, b, c)
    orq.responder("p", "Q07")
    texto = log.read_text(encoding="utf-8")
    assert "SEGREDO" not in texto and "Incorrect API key" not in texto
    regs = ler(log)
    tent = [r for r in regs if r["evento"] == "tentativa"]
    assert tent[0]["erro_tipo"] == "AuthenticationError" and tent[0]["status_http"] == 401
    assert tent[1]["tokens_in"] == 100 and tent[1]["tokens_out"] == 20 and tent[1]["prompt_versao"] == "v1"
    final = regs[-1]
    assert final["evento"] == "final" and final["prompt_versao"] == "v1" and final["pergunta_id"] == "Q07"
    assert final["rota"] == ["anthropic", "openai"] and final["tentativas"] == 2


def test_todo_registro_tem_pergunta_id_e_evento(tmp_path):
    b = AgenteFalso("anthropic", [ok("anthropic", confianca="baixa")])
    c = AgenteFalso("openai", [ok("openai")])
    orq, _, log = montar(tmp_path, b, c)
    orq.responder("p", "Q03")
    assert all(r["pergunta_id"] == "Q03" and r["evento"] for r in ler(log))


def test_ordem_invalida_e_rejeitada(tmp_path):
    b = AgenteFalso("anthropic", [])
    with pytest.raises(ValueError):
        Orquestrador({"anthropic": b}, ["anthropic", "openai"], Politica())


# --- integração: agentes reais + clientes falsos que lançam exceções do tipo do SDK --------

from src.agentes.anthropic_agente import AgenteAnthropic  # noqa: E402
from src.agentes.openai_agente import AgenteOpenAI  # noqa: E402
from tests.fakes import AnthropicRoteirizado, OpenAIRoteirizado, anthropic_msg, openai_resp  # noqa: E402
from tests.test_agentes import CONSULTA, FINAL_OK, ambiente  # noqa: E402,F401


class AnthropicQueFalha(AnthropicRoteirizado):
    """Levanta a 1a exceção do roteiro e, depois, segue o roteiro normal."""

    def __init__(self, excecoes, respostas):
        super().__init__(respostas)
        self.excecoes = list(excecoes)
        self.messages.create = self._create_falho

    def _create_falho(self, **kw):
        if self.excecoes:
            raise self.excecoes.pop(0)
        return self._create(**kw)


def test_integracao_timeout_real_do_agente_dispara_retry_e_depois_funciona(ambiente, tmp_path):
    s, tabela, controle, buscador, prompt, _ = ambiente
    cli = AnthropicQueFalha([_exc("APITimeoutError")], [
        anthropic_msg(stop_reason="tool_use", blocos=[("tool_use", "tu_1", {"consulta": CONSULTA})]),
        anthropic_msg(stop_reason="end_turn", blocos=[("text", FINAL_OK)]),
    ])
    ag_a = AgenteAnthropic(s, controle, buscador, tabela, prompt, client=cli)
    ag_o = AgenteOpenAI(s, controle, buscador, tabela, prompt, client=OpenAIRoteirizado([]))
    rel = Relogio()
    orq = Orquestrador({"anthropic": ag_a, "openai": ag_o}, ["anthropic", "openai"], Politica(),
                       LogRoteamento(tmp_path / "r.jsonl"), dormir=rel.dormir, relogio=rel.agora)
    res = orq.responder("Com que frequência os acessos privilegiados são revisados?", "Q01")
    assert res.status == ACEITA_NO_PRIMEIRO and res.provedor_final == "anthropic"
    assert rel.esperas == [1.0] and len(res.tentativas) == 2
    assert res.tentativas[0].falha.value == "transitoria" and res.tentativas[0].erro_tipo == "APITimeoutError"
    assert res.final.prompt_versao == "agente_resposta_v1"


def test_integracao_teto_de_gasto_real_faz_fallback(ambiente, tmp_path):
    from src.config import carregar_settings
    from src.custo import ControleCusto
    s, tabela, _, buscador, prompt, _ = ambiente
    s2 = carregar_settings(env={"BUDGET_ANTHROPIC_USD": "0.000001"}, usar_dotenv=False)
    controle = ControleCusto(tabela, s2.orcamentos(), tmp_path / "c2.jsonl")
    cli_a = AnthropicRoteirizado([])   # nunca deve ser chamado: o teto bloqueia antes
    cli_o = OpenAIRoteirizado([
        openai_resp(id="r1", chamadas=[("c", {"consulta": CONSULTA})]), openai_resp(id="r2", texto=FINAL_OK)])
    ag_a = AgenteAnthropic(s2, controle, buscador, tabela, prompt, client=cli_a)
    ag_o = AgenteOpenAI(s2, controle, buscador, tabela, prompt, client=cli_o)
    orq = Orquestrador({"anthropic": ag_a, "openai": ag_o}, ["anthropic", "openai"], Politica(),
                       LogRoteamento(tmp_path / "r2.jsonl"), dormir=lambda s: None)
    res = orq.responder("p", "Q01")
    assert res.provedor_final == "openai" and res.motivo_escalonamento == "orcamento_excedido"
    assert cli_a.pedidos == []
    bloqueios = [json.loads(l) for l in (tmp_path / "c2.jsonl").read_text(encoding="utf-8").splitlines()
                 if "bloqueado_orcamento" in l]
    assert len(bloqueios) == 1 and bloqueios[0]["provedor"] == "anthropic"
