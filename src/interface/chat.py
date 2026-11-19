"""Lógica do chat sem Gradio: mensagens, trecho da fonte, arquivos para download e sugestões.

Fica fora de ui.py para ser testável sem a biblioteca de interface. A tela só liga estas funções aos componentes.
Cada pergunta é independente: o serviço não recebe o histórico, então o chat não tem memória entre perguntas.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import RAIZ
from .formatar import CONFIANCA
from .servico import RespostaDemo, ServicoDemo

DIR_DOCS = RAIZ / "dados" / "documentos"
ARQ_PERGUNTAS = RAIZ / "dados" / "perguntas.json"
_ID_DOC = re.compile(r"^POL-[A-Z]{3}$")
_ID_SECAO = re.compile(r"^[A-Z]{3}-\d{1,2}$")
MAX_TRECHO = 450
MAX_FONTES = 3
ESPERA = "_Buscando nos documentos…_"
BLOQUEIOS = ("limite_visitante", "limite_global", "teto_custo")


# --- documentos e trechos ----------------------------------------------------------------

def arquivo_do_documento(documento: str | None, dir_docs: Path = DIR_DOCS) -> Path | None:
    """Caminho do .md de um documento (ex.: POL-ACE). O identificador é validado antes de montar o padrão de busca."""
    if not documento or not _ID_DOC.match(documento):
        return None
    achados = sorted(dir_docs.glob(f"{documento}_*.md"))
    return achados[0] if achados else None


def carregar_secao(documento: str, secao: str, dir_docs: Path = DIR_DOCS) -> tuple[str, str] | None:
    """(título, texto) de uma seção `## ACE-3 Título`, com o texto em uma linha e limitado a MAX_TRECHO."""
    caminho = arquivo_do_documento(documento, dir_docs)
    if caminho is None or not _ID_SECAO.match(secao or ""):
        return None
    prefixo = f"## {secao} "
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith(prefixo)), None)
    if inicio is None:
        return None
    titulo = linhas[inicio][len(prefixo):].strip()
    corpo: list[str] = []
    for linha in linhas[inicio + 1:]:
        if linha.startswith("## "):
            break
        corpo.append(linha)
    texto = " ".join(" ".join(corpo).split())
    if len(texto) > MAX_TRECHO:
        texto = texto[:MAX_TRECHO].rstrip() + "…"
    return titulo, texto


def documentos_citados(citacoes: list[dict[str, str]], dir_docs: Path = DIR_DOCS) -> list[Path]:
    """Arquivos dos documentos citados, sem repetir e na ordem de citação; ignora o que não existe."""
    vistos: list[str] = []
    for c in citacoes:
        if c.get("documento") not in vistos:
            vistos.append(c.get("documento", ""))
    caminhos = (arquivo_do_documento(d, dir_docs) for d in vistos)
    return [c for c in caminhos if c is not None]


# --- mensagens ---------------------------------------------------------------------------

def _bloco_fontes(citacoes: list[dict[str, str]], dir_docs: Path) -> str:
    unicas: list[tuple[str, str]] = []
    for c in citacoes:
        par = (c.get("documento", ""), c.get("secao", ""))
        if par not in unicas:
            unicas.append(par)
    if not unicas:
        return "_Nenhuma fonte citada._"
    blocos: list[str] = []
    for doc, sec in unicas[:MAX_FONTES]:
        achada = carregar_secao(doc, sec, dir_docs)
        if achada is None:
            blocos.append(f"> **{doc} · {sec}**")
            continue
        titulo, texto = achada
        blocos.append(f"> **{doc} · {sec}** — {titulo}\n>\n> {texto}")
    if len(unicas) > MAX_FONTES:
        blocos.append(f"_(+{len(unicas) - MAX_FONTES} fonte(s) não exibida(s))_")
    return "\n\n".join(blocos)


AVISOS_ORQUESTRACAO = {
    "aceita_por_consenso": "_Confirmada por dois provedores: mesmas fontes e mesmos valores._",
    "divergencia": ("_Atenção: os dois provedores divergiram em fontes ou valores. Confira o trecho no "
                    "documento antes de usar esta resposta._"),
}


def _rodape(r: RespostaDemo) -> str:
    conf = CONFIANCA.get(r.confianca or "", "-")
    if r.status == "cache":
        return f"_Confiança: {conf} · resposta em cache (sem custo)_"
    return f"_Confiança: {conf} · {r.provedor} · US$ {r.custo_usd:.6f} · {r.latencia_s:.1f}s_"


def montar_mensagem(r: RespostaDemo, dir_docs: Path = DIR_DOCS) -> str:
    """Markdown da bolha do assistente."""
    if not r.ok:
        return f"⚠️ **{r.mensagem}**"
    partes = [r.resposta or ""]
    if r.status_orq == "nao_encontrado_confirmado":
        partes.append("_Os dois provedores confirmaram: a base não traz essa informação._")
    elif r.encontrado is False:
        partes.append("_A base não traz essa informação com segurança._")
    partes.append(_bloco_fontes(r.citacoes, dir_docs))
    aviso = AVISOS_ORQUESTRACAO.get(r.status_orq)
    if aviso:
        partes.append(aviso)
    elif not r.aceita_pela_regra:
        partes.append("_Atenção: nenhum dos provedores passou na regra de qualidade; esta é a melhor resposta obtida._")
    partes.append(_rodape(r))
    return "\n\n".join(partes)


def status_restantes(restantes: int, total: int) -> str:
    return f"Perguntas restantes hoje: **{restantes}** de {total}"


# --- sugestões ---------------------------------------------------------------------------

def carregar_perguntas(caminho: Path = ARQ_PERGUNTAS) -> list[dict[str, Any]]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _norm(texto: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", texto.casefold()).split())


def sugestoes_iniciais(perguntas: list[dict[str, Any]], n: int = 6) -> list[str]:
    """Uma pergunta por documento (os primeiros n), para mostrar a variedade da base."""
    vistos: set[str] = set()
    saida: list[str] = []
    for q in perguntas:
        if q["documento"] in vistos:
            continue
        vistos.add(q["documento"])
        saida.append(q["pergunta"])
        if len(saida) == n:
            break
    return saida


def sugestoes_seguimento(perguntas: list[dict[str, Any]], documentos: set[str], ja_feitas: list[str],
                         n: int = 3) -> list[str]:
    """Até 2 perguntas do mesmo documento da resposta, depois de outros documentos; nunca repete o que já foi perguntado."""
    feitas = {_norm(p) for p in ja_feitas}
    pendentes = [q for q in perguntas if _norm(q["pergunta"]) not in feitas]
    mesmos = [q for q in pendentes if q["documento"] in documentos]
    outros: list[dict[str, Any]] = []
    vistos = set(documentos)
    for q in pendentes:
        if q["documento"] not in vistos:
            vistos.add(q["documento"])
            outros.append(q)
    return [q["pergunta"] for q in (mesmos[:2] + outros)[:n]]


# --- um turno do chat --------------------------------------------------------------------

@dataclass
class Turno:
    historico: list[dict[str, str]]
    sugestoes: list[str] = field(default_factory=list)
    arquivos: list[str] = field(default_factory=list)
    status: str = ""


def perguntas_do_usuario(historico: list[dict[str, Any]]) -> list[str]:
    return [m["content"] for m in historico if m.get("role") == "user" and isinstance(m.get("content"), str)]


def iniciar_turno(historico: list[dict[str, Any]] | None, pergunta: str) -> list[dict[str, str]]:
    """Histórico com a pergunta do usuário e o aviso de espera, para mostrar antes da resposta chegar."""
    return [*(historico or []), {"role": "user", "content": pergunta}, {"role": "assistant", "content": ESPERA}]


def concluir_turno(servico: ServicoDemo, pergunta: str, visitante: str, historico: list[dict[str, Any]] | None,
                   perguntas: list[dict[str, Any]], *, por_visitante: int, n_iniciais: int = 6,
                   dir_docs: Path = DIR_DOCS) -> Turno:
    r = servico.perguntar(pergunta, visitante)
    novo = [*(historico or []), {"role": "user", "content": pergunta},
            {"role": "assistant", "content": montar_mensagem(r, dir_docs)}]
    if r.status in BLOQUEIOS:
        sugestoes: list[str] = []
    elif r.ok:
        docs = {c["documento"] for c in r.citacoes}
        sugestoes = sugestoes_seguimento(perguntas, docs, perguntas_do_usuario(novo))
    else:
        sugestoes = sugestoes_iniciais(perguntas, n_iniciais)
    arquivos = [str(p) for p in documentos_citados(r.citacoes, dir_docs)] if r.ok else []
    return Turno(novo, sugestoes, arquivos, status_restantes(r.restantes_visitante, por_visitante))
