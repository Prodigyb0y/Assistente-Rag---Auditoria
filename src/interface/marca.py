"""Marca fictícia da Gutenberg Systems usada na demo (ícone do cabeçalho).

O SVG fica em docs/img/marca/icone.svg. Para o CSS, tiramos só o bloco <metadata> (manifesto de proveniência, ~7 KB),
que não desenha nada; o arquivo versionado continua intacto. Se o arquivo não existir (ex.: pasta docs ausente), a demo
mantém o quadrado de gradiente original: a marca é enfeite, nunca motivo para a tela falhar.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

ICONE = Path(__file__).resolve().parents[2] / "docs" / "img" / "marca" / "icone.svg"
_METADATA = re.compile(r"<metadata\b.*?</metadata>", re.DOTALL | re.IGNORECASE)


def icone_data_uri(caminho: Path = ICONE) -> str | None:
    """Data URI do ícone sem o bloco <metadata>, ou None se o arquivo não existir ou não parecer um SVG simples."""
    try:
        svg = caminho.read_text(encoding="utf-8")
    except OSError:
        return None
    svg = _METADATA.sub("", svg).strip()
    baixo = svg.lower()
    if not baixo.startswith("<svg") or "<script" in baixo or "foreignobject" in baixo or "href=" in baixo:
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def css_marca(caminho: Path = ICONE) -> str:
    """Regra de CSS que troca o quadrado do título pelo ícone; vazia se o ícone não estiver disponível."""
    uri = icone_data_uri(caminho)
    if uri is None:
        return ""
    return ('#cabecalho h1::before { width: 1.15em; height: 1.15em; vertical-align: -.2em; border-radius: 0; box-shadow: none;'
            f' background: url("{uri}") center / contain no-repeat; }}\n')
