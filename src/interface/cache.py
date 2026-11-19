"""Cache de respostas da demo: pergunta normalizada + versão do prompt + modelos -> resposta.

Só respostas ACEITAS pela regra de roteamento são guardadas. Cache hit não consome limite nem custo.
A chave inclui a versão do prompt e os modelos: mudar qualquer um invalida as entradas antigas.
LIMITAÇÃO: com disco efêmero o arquivo some quando o Space reinicia (o cache recomeça vazio).
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from ..avaliacao.acerto import normalizar


def chave_cache(pergunta: str, prompt_versao: str, modelos: str) -> str:
    base = normalizar(pergunta).strip(" ?!.\t\n")
    return hashlib.sha256(f"{prompt_versao}|{modelos}|{base}".encode()).hexdigest()


class CacheRespostas:
    def __init__(self, caminho: Path | None, max_itens: int = 500):
        self.caminho, self.max_itens = (Path(caminho) if caminho else None), max_itens
        self._trava = threading.Lock()
        self._d: dict[str, Any] = {}
        if self.caminho and self.caminho.exists():
            try:
                self._d = json.loads(self.caminho.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._d = {}

    def __len__(self) -> int:
        return len(self._d)

    def obter(self, chave: str) -> Any | None:
        with self._trava:
            return self._d.get(chave)

    def guardar(self, chave: str, valor: Any) -> None:
        with self._trava:
            if chave not in self._d and len(self._d) >= self.max_itens:
                self._d.pop(next(iter(self._d)))   # descarta a mais antiga
            self._d[chave] = valor
            if self.caminho:
                self.caminho.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.caminho.with_suffix(".tmp")
                tmp.write_text(json.dumps(self._d, ensure_ascii=False), encoding="utf-8")
                tmp.replace(self.caminho)
