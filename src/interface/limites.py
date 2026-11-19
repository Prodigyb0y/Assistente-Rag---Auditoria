"""Limites da demo pública: perguntas por dia (por visitante e global) e teto de custo diário.

- O visitante é identificado por um HASH do IP com sal (sha256). O IP puro nunca é gravado.
- O "dia" usa o fuso de Brasília (UTC-3, sem horário de verão desde 2019), sem depender de tzdata.
- O estado fica num arquivo JSON, com trava para chamadas simultâneas.
- LIMITAÇÃO: em hospedagem com disco efêmero (Hugging Face Spaces sem armazenamento persistente) o
  arquivo some quando o Space reinicia, e os contadores voltam a zero. Por isso o teto de gasto
  também precisa existir FORA do código: limite de gasto configurado nos consoles da OpenAI e da
  Anthropic.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

BRASILIA = timezone(timedelta(hours=-3))


def hoje_brasilia() -> str:
    return datetime.now(BRASILIA).strftime("%Y-%m-%d")


def id_visitante(ip: str, sal: str) -> str:
    return hashlib.sha256(f"{sal}|{ip}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Decisao:
    permitido: bool
    motivo: str | None            # None | "limite_visitante" | "limite_global" | "teto_custo"
    restantes_visitante: int
    restantes_global: int


class LimiteDiario:
    def __init__(self, caminho: Path | None, por_visitante: int, global_dia: int, teto_custo_usd: float,
                 hoje: Callable[[], str] = hoje_brasilia):
        self.caminho = Path(caminho) if caminho else None
        self.por_visitante, self.global_dia, self.teto_custo_usd = por_visitante, global_dia, teto_custo_usd
        self._hoje = hoje
        self._trava = threading.Lock()
        self._estado = self._carregar()

    def _vazio(self, dia: str) -> dict:
        return {"dia": dia, "global": 0, "custo_usd": 0.0, "visitantes": {}}

    def _carregar(self) -> dict:
        dia = self._hoje()
        if self.caminho and self.caminho.exists():
            try:
                e = json.loads(self.caminho.read_text(encoding="utf-8"))
                if e.get("dia") == dia:
                    return e
            except (json.JSONDecodeError, OSError):
                pass
        return self._vazio(dia)

    def _salvar(self) -> None:
        if self.caminho:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.caminho.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._estado, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.caminho)

    def _virar_dia(self) -> None:
        if self._estado["dia"] != self._hoje():
            self._estado = self._vazio(self._hoje())

    def _restantes(self, visitante: str) -> tuple[int, int]:
        usado = self._estado["visitantes"].get(visitante, 0)
        return max(0, self.por_visitante - usado), max(0, self.global_dia - self._estado["global"])

    def consultar(self, visitante: str) -> Decisao:
        with self._trava:
            self._virar_dia()
            rv, rg = self._restantes(visitante)
            return Decisao(True, None, rv, rg)

    def reservar(self, visitante: str) -> Decisao:
        """Consome 1 pergunta se houver folga. Chame ANTES de gastar com a API."""
        with self._trava:
            self._virar_dia()
            rv, rg = self._restantes(visitante)
            if self._estado["custo_usd"] >= self.teto_custo_usd:
                return Decisao(False, "teto_custo", rv, rg)
            if rg <= 0:
                return Decisao(False, "limite_global", rv, rg)
            if rv <= 0:
                return Decisao(False, "limite_visitante", rv, rg)
            self._estado["global"] += 1
            self._estado["visitantes"][visitante] = self._estado["visitantes"].get(visitante, 0) + 1
            self._salvar()
            return Decisao(True, None, rv - 1, rg - 1)

    def estornar(self, visitante: str) -> None:
        """Devolve a pergunta quando nenhuma resposta foi obtida (falha dos dois provedores)."""
        with self._trava:
            self._virar_dia()
            if self._estado["visitantes"].get(visitante, 0) > 0:
                self._estado["visitantes"][visitante] -= 1
                self._estado["global"] = max(0, self._estado["global"] - 1)
                self._salvar()

    def registrar_custo(self, custo_usd: float) -> None:
        with self._trava:
            self._virar_dia()
            self._estado["custo_usd"] += custo_usd
            self._salvar()

    @property
    def custo_hoje_usd(self) -> float:
        with self._trava:
            self._virar_dia()
            return self._estado["custo_usd"]


def extrair_ip(cabecalhos: dict | None, host: str | None) -> str:
    """IP do visitante. Atrás de proxy usa a ÚLTIMA entrada de X-Forwarded-For (a que o proxy mais próximo
    anexou); a primeira pode ser forjada pelo cliente. É um limite de melhor esforço: o limite global e o
    teto de custo diário são as barreiras que não dependem desta identificação."""
    xff = (cabecalhos or {}).get("x-forwarded-for", "")
    ips = [p.strip() for p in xff.split(",") if p.strip()]
    return ips[-1] if ips else (host or "desconhecido")
