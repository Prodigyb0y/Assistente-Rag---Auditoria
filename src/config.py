"""Configuração tipada, lida de variáveis de ambiente (e de .env em desenvolvimento).

As chaves nunca são impressas nem logadas: ficam em SecretStr.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr

RAIZ = Path(__file__).resolve().parent.parent

PROVEDORES = ("openai", "anthropic")


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida. A mensagem nunca contém valores de chaves."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    openai_model: str = "gpt-6.1-terra"
    anthropic_model: str = "claude-haiku-5-5"
    embedding_model: str = "text-embedding-3-small"

    budget_openai_usd: float = Field(4.0, gt=0)
    budget_anthropic_usd: float = Field(4.0, gt=0)

    timeout_s: float = Field(30.0, gt=0)
    max_output_tokens: int = Field(512, gt=0, le=8192)
    # Agentes: limite maior, porque modelos com raciocínio gastam tokens de saída pensando.
    agent_max_output_tokens: int = Field(4096, gt=0, le=32000)

    # Orquestração (Bloco 5)
    max_tentativas: int = Field(3, ge=1, le=6)          # tentativas por provedor (1 + retries)
    espera_base_s: float = Field(1.0, ge=0)             # backoff: base * 2**(tentativa-1)
    espera_max_s: float = Field(8.0, ge=0)              # teto da espera entre tentativas
    prazo_total_s: float = Field(120.0, gt=0)           # prazo por pergunta (não interrompe chamada em curso)
    confianca_minima: Literal["baixa", "media", "alta"] = "media"  # abaixo disto, escala
    # escalonar = regra original; adaptativo = caminho conforme o sinal; consenso = os dois sempre respondem
    orquestracao_modo: Literal["escalonar", "adaptativo", "consenso"] = "adaptativo"

    log_dir: Path = RAIZ / "logs"
    precos_path: Path = RAIZ / "config" / "precos.json"

    def chave(self, provedor: str) -> str:
        valor = {"openai": self.openai_api_key, "anthropic": self.anthropic_api_key}.get(provedor)
        if valor is None or not valor.get_secret_value().strip():
            nome = f"{provedor.upper()}_API_KEY"
            raise ConfigError(f"Variável de ambiente {nome} não definida.")
        return valor.get_secret_value()

    def modelo(self, provedor: str) -> str:
        return {"openai": self.openai_model, "anthropic": self.anthropic_model}[provedor]

    def orcamentos(self) -> dict[str, float]:
        return {"openai": self.budget_openai_usd, "anthropic": self.budget_anthropic_usd}


_ENV_PARA_CAMPO = {
    "OPENAI_API_KEY": "openai_api_key",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "OPENAI_MODEL": "openai_model",
    "ANTHROPIC_MODEL": "anthropic_model",
    "EMBEDDING_MODEL": "embedding_model",
    "BUDGET_OPENAI_USD": "budget_openai_usd",
    "BUDGET_ANTHROPIC_USD": "budget_anthropic_usd",
    "TIMEOUT_S": "timeout_s",
    "MAX_OUTPUT_TOKENS": "max_output_tokens",
    "AGENT_MAX_OUTPUT_TOKENS": "agent_max_output_tokens",
    "MAX_TENTATIVAS": "max_tentativas",
    "ESPERA_BASE_S": "espera_base_s",
    "ESPERA_MAX_S": "espera_max_s",
    "PRAZO_TOTAL_S": "prazo_total_s",
    "CONFIANCA_MINIMA": "confianca_minima",
    "ORQUESTRACAO_MODO": "orquestracao_modo",
    "LOG_DIR": "log_dir",
}


def carregar_settings(env: Mapping[str, str] | None = None, usar_dotenv: bool = True) -> Settings:
    """Lê Settings. Passe `env` nos testes; em uso normal lê os.environ (+ .env)."""
    if env is None:
        if usar_dotenv:
            from dotenv import load_dotenv

            load_dotenv(RAIZ / ".env", override=False)
        env = os.environ
    dados = {campo: env[nome] for nome, campo in _ENV_PARA_CAMPO.items() if env.get(nome)}
    try:
        return Settings(**dados)
    except Exception as exc:  # pydantic.ValidationError: não repetir valores na mensagem
        campos = sorted({str(e["loc"][0]) for e in getattr(exc, "errors", lambda: [])()})
        raise ConfigError(f"Configuração inválida nos campos: {', '.join(campos) or 'desconhecido'}") from None
