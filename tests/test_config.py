import pytest

from src.config import ConfigError, carregar_settings


def test_defaults_sem_chaves():
    s = carregar_settings(env={}, usar_dotenv=False)
    assert s.budget_openai_usd == 4.0 and s.budget_anthropic_usd == 4.0
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        s.chave("openai")


def test_le_variaveis_e_converte_tipos():
    s = carregar_settings(env={"ANTHROPIC_API_KEY": "sk-teste", "BUDGET_OPENAI_USD": "2.5", "TIMEOUT_S": "10"},
                          usar_dotenv=False)
    assert s.chave("anthropic") == "sk-teste"
    assert s.budget_openai_usd == 2.5 and s.timeout_s == 10.0


def test_chave_nunca_aparece_em_repr():
    s = carregar_settings(env={"OPENAI_API_KEY": "sk-segredo-123"}, usar_dotenv=False)
    assert "sk-segredo-123" not in repr(s) and "sk-segredo-123" not in str(s)


def test_valor_invalido_nao_vaza_na_mensagem():
    with pytest.raises(ConfigError) as e:
        carregar_settings(env={"BUDGET_OPENAI_USD": "-5", "OPENAI_API_KEY": "sk-segredo-123"}, usar_dotenv=False)
    assert "budget_openai_usd" in str(e.value) and "sk-segredo-123" not in str(e.value)
