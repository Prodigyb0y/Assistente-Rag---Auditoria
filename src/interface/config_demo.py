"""Configuração da demo (limites), lida de variáveis de ambiente / secrets da plataforma."""
from __future__ import annotations

import os
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..config import ConfigError


class ConfigDemo(BaseModel):
    model_config = ConfigDict(frozen=True)

    por_visitante_dia: int = Field(5, ge=1)
    global_dia: int = Field(60, ge=1)
    teto_custo_dia_usd: float = Field(0.25, gt=0)
    max_chars: int = Field(300, ge=20, le=2000)
    sal: SecretStr = SecretStr("troque-este-sal")   # defina DEMO_SALT nos secrets em produção

    @property
    def sal_padrao(self) -> bool:
        return self.sal.get_secret_value() == "troque-este-sal"


_ENV = {"DEMO_POR_VISITANTE_DIA": "por_visitante_dia", "DEMO_GLOBAL_DIA": "global_dia",
        "DEMO_TETO_CUSTO_DIA_USD": "teto_custo_dia_usd", "DEMO_MAX_CHARS": "max_chars", "DEMO_SALT": "sal"}


def carregar_config_demo(env: Mapping[str, str] | None = None) -> ConfigDemo:
    env = os.environ if env is None else env
    dados = {campo: env[nome] for nome, campo in _ENV.items() if env.get(nome)}
    try:
        return ConfigDemo(**dados)
    except Exception as exc:
        campos = sorted({str(e["loc"][0]) for e in getattr(exc, "errors", lambda: [])()})
        raise ConfigError(f"Configuração da demo inválida nos campos: {', '.join(campos) or 'desconhecido'}") from None
