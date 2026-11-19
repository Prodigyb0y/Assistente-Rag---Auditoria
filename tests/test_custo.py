import json
from types import SimpleNamespace

import pytest

from src.config import carregar_settings
from src.custo import ControleCusto, ModeloSemPreco, OrcamentoExcedido, TabelaPrecos
from src.provedores import chamar_anthropic, chamar_openai

RAIZ_PRECOS = "config/precos.json"


@pytest.fixture
def tabela():
    return TabelaPrecos.de_json(RAIZ_PRECOS)


def ler_log(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


def test_custo_basico(tabela):
    # 1M entrada + 1M saída no Sonnet 5.5 = 2 + 10 USD
    assert tabela.get("claude-sonnet-5-5").custo(1_000_000, 1_000_000) == pytest.approx(12.0)
    # embedding: só entrada
    assert tabela.get("text-embedding-3-small").custo(1_000_000, 0) == pytest.approx(0.02)


def test_faixa_acima_do_limite(tabela):
    haiku = tabela.get("claude-haiku-5-5")
    assert haiku.custo(100_000, 0) == pytest.approx(0.01)   # no limite: preço base
    assert haiku.custo(100_001, 0) == pytest.approx(100_001 / 1e6 * 0.50)  # acima: preço alto


def test_modelo_sem_preco(tabela):
    with pytest.raises(ModeloSemPreco):
        tabela.get("modelo-inexistente")


def test_bloqueia_antes_de_estourar_e_loga(tabela, tmp_path):
    log = tmp_path / "c.jsonl"
    c = ControleCusto(tabela, {"anthropic": 0.001}, log)
    with pytest.raises(OrcamentoExcedido):
        # pior caso: 4000 tokens de saída no Sonnet = 0.04 USD > 0.001
        c.reservar("anthropic", "claude-sonnet-5-5", 100, 4000)
    reg = ler_log(log)
    assert reg[-1]["status"] == "bloqueado_orcamento" and reg[-1]["tokens_in"] == 0


def test_teto_persiste_entre_execucoes(tabela, tmp_path):
    log = tmp_path / "c.jsonl"
    c1 = ControleCusto(tabela, {"anthropic": 0.01}, log)
    c1.registrar("anthropic", "claude-sonnet-5-5", 500, 500, 0.1)  # 0.006 USD
    c2 = ControleCusto(tabela, {"anthropic": 0.01}, log)            # novo processo
    assert c2.gasto("anthropic") == pytest.approx(0.006)
    with pytest.raises(OrcamentoExcedido):
        c2.reservar("anthropic", "claude-sonnet-5-5", 4000, 500)


class _OpenAIFalso:
    def __init__(self):
        self.chamadas = 0
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.chamadas += 1
        return SimpleNamespace(output_text="ok", usage=SimpleNamespace(input_tokens=12, output_tokens=3))


class _AnthropicFalso:
    def __init__(self):
        self.chamadas = 0
        self.kwargs = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.chamadas += 1
        self.kwargs = kw
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")],
                               usage=SimpleNamespace(input_tokens=15, output_tokens=2))


def test_chamadas_registram_tokens_e_custo(tabela, tmp_path):
    s = carregar_settings(env={}, usar_dotenv=False)
    c = ControleCusto(tabela, s.orcamentos(), tmp_path / "c.jsonl")
    r1 = chamar_openai("oi", s, c, client=_OpenAIFalso())
    r2 = chamar_anthropic("oi", s, c, client=_AnthropicFalso())
    assert (r1.tokens_in, r1.tokens_out) == (12, 3)
    assert (r2.tokens_in, r2.tokens_out) == (15, 2)
    reg = ler_log(tmp_path / "c.jsonl")
    assert [r["status"] for r in reg] == ["ok", "ok"]
    assert all("tokens_in" in r and "tokens_out" in r for r in reg)


def test_chamada_bloqueada_nao_chega_ao_cliente(tabela, tmp_path):
    env = {"BUDGET_ANTHROPIC_USD": "0.000001"}
    s = carregar_settings(env=env, usar_dotenv=False)
    c = ControleCusto(tabela, s.orcamentos(), tmp_path / "c.jsonl")
    falso = _AnthropicFalso()
    with pytest.raises(OrcamentoExcedido):
        chamar_anthropic("oi", s, c, client=falso)
    assert falso.chamadas == 0


def test_nao_envia_parametros_de_amostragem_para_anthropic(tabela, tmp_path):
    s = carregar_settings(env={}, usar_dotenv=False)
    c = ControleCusto(tabela, s.orcamentos(), tmp_path / "c.jsonl")
    falso = _AnthropicFalso()
    chamar_anthropic("oi", s, c, client=falso)
    assert not {"temperature", "top_p", "top_k"} & set(falso.kwargs)


def test_erro_da_api_e_logado_e_repropagado(tabela, tmp_path):
    s = carregar_settings(env={}, usar_dotenv=False)
    c = ControleCusto(tabela, s.orcamentos(), tmp_path / "c.jsonl")

    class Quebrado:
        responses = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(TimeoutError("t")))

    with pytest.raises(TimeoutError):
        chamar_openai("oi", s, c, client=Quebrado())
    assert ler_log(tmp_path / "c.jsonl")[-1]["status"] == "erro"
    assert c.gasto("openai") == 0.0
