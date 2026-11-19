"""Monta o serviço da demo (o que o app.py usa). Em hospedagem nova, o índice é criado na partida."""
from __future__ import annotations

from pathlib import Path

from ..agentes.anthropic_agente import AgenteAnthropic
from ..agentes.openai_agente import AgenteOpenAI
from ..agentes.prompts import carregar_prompt
from ..config import RAIZ, Settings
from ..custo import ControleCusto, TabelaPrecos
from ..ingestao.chunker import carregar_documentos
from ..ingestao.embeddings import Embedder, OpenAIEmbedder
from ..ingestao.indexador import carregar_indice, ingerir
from ..orquestrador.orquestrador import LogRoteamento, Orquestrador
from ..orquestrador.politica import Politica, ordem_por_preco
from ..recuperacao.buscador import Buscador
from .cache import CacheRespostas
from .config_demo import ConfigDemo
from .limites import LimiteDiario
from .servico import ServicoDemo


def garantir_indice(dir_indice: Path, dir_docs: Path, embedder: Embedder) -> str:
    """Cria o índice se não existir (ex.: Space novo, onde indice/ não vai para o Git). Idempotente:
    se já existir, não chama a API. Devolve 'existente' ou 'criado'."""
    if (dir_indice / "chunks.json").exists() and (dir_indice / "vetores.npy").exists():
        return "existente"
    ingerir(carregar_documentos(dir_docs), dir_indice, embedder)
    return "criado"


def montar_servico(s: Settings, cfg: ConfigDemo) -> ServicoDemo:
    tabela = TabelaPrecos.de_json(s.precos_path)
    controle = ControleCusto(tabela, s.orcamentos(), s.log_dir / "chamadas.jsonl")
    embedder = OpenAIEmbedder(s, controle)
    garantir_indice(RAIZ / "indice", RAIZ / "dados" / "documentos", embedder)
    buscador = Buscador(carregar_indice(RAIZ / "indice"), embedder)
    prompt = carregar_prompt()
    agentes = {"openai": AgenteOpenAI(s, controle, buscador, tabela, prompt),
               "anthropic": AgenteAnthropic(s, controle, buscador, tabela, prompt)}
    modelos = {"openai": s.openai_model, "anthropic": s.anthropic_model}
    orq = Orquestrador(agentes, ordem_por_preco(tabela, modelos), Politica.de_settings(s),
                       LogRoteamento(s.log_dir / "demo_roteamento.jsonl"))
    demo_dir = s.log_dir / "demo"
    limites = LimiteDiario(demo_dir / "limites.json", cfg.por_visitante_dia, cfg.global_dia, cfg.teto_custo_dia_usd)
    cache = CacheRespostas(demo_dir / "cache.json")
    return ServicoDemo(orq, limites, cache, prompt_versao=prompt.versao,
                       modelos=f"{s.openai_model}+{s.anthropic_model}", max_chars=cfg.max_chars)
