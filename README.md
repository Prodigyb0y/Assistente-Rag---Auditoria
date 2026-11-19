---
title: Busca em políticas de auditoria (demo)
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.30.0
python_version: "3.11"
app_file: app.py
pinned: false
short_description: RAG de auditoria com OpenAI e Anthropic (dados fictícios)
---

# Busca em políticas de auditoria — demo

Assistente que responde perguntas de apoio a um auditor interno **citando a seção de origem**, orquestrando
**OpenAI** e **Anthropic**. Projeto de portfólio.

![Demo em formato de chat](docs/img/demo.png)

- **Dados 100% fictícios** (empresa fictícia Gutenberg Systems). O sistema é apoio à busca: **não é decisão de auditoria**.
- **Como funciona:** recuperação por embeddings, agente com tool calling, regra de roteamento em código entre os dois
  provedores e citação verificada contra o que foi recuperado.
- **Limites da demo:** 5 perguntas por visitante por dia, teto de custo diário e cache de respostas repetidas.
- A aba **Sobre o projeto** explica o que o assistente faz e por que existe.
- Este Space é só a hospedagem da demo; os modelos continuam sendo OpenAI e Anthropic.

**Documentação completa, arquitetura, resultados medidos e limitações:**
[github.com/Prodigyb0y/Assistente-Rag---Auditoria](https://github.com/Prodigyb0y/Assistente-Rag---Auditoria)
