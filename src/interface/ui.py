"""Tela Gradio da demo, em formato de chat. Fina de propósito: a regra está em servico.py e chat.py (testados).

No Gradio 6, `theme` e `css` vão em `launch()` (não em `Blocks`): use `opcoes_launch()` no app.py.
"""
from __future__ import annotations

import gradio as gr

from .chat import (DIR_DOCS, Turno, carregar_perguntas, concluir_turno, iniciar_turno, status_restantes,
                   sugestoes_iniciais)
from .config_demo import ConfigDemo
from .formatar import AVISO
from .limites import extrair_ip, id_visitante
from .servico import ServicoDemo

N_CHIPS = 6

CSS = """
/* ---------- paleta própria (claro e escuro), independente da do Hugging Face ---------- */
:root, .gradio-container {
  --app-bg: #eceff6; --surface: #ffffff; --surface-2: #f3f5fb; --borda: #c6cee0;
  --texto: #1b2133; --texto-suave: #556078; --acento: #4f46e5; --acento-2: #8b5cf6;
  --halo: rgba(79,70,229,.13); --sombra: rgba(15,23,42,.14); --sombra-suave: rgba(15,23,42,.06);
}
.dark, .dark .gradio-container {
  --app-bg: #080b11; --surface: #141a27; --surface-2: #1c2435; --borda: #36435e;
  --texto: #e8ecf6; --texto-suave: #9aa6bf; --acento: #818cf8; --acento-2: #a78bfa;
  --halo: rgba(129,140,248,.16); --sombra: rgba(0,0,0,.5); --sombra-suave: rgba(0,0,0,.25);
}
html, body { background: var(--app-bg) !important; }
.gradio-container { max-width: 1240px !important; margin: 0 auto !important; padding: 1rem 1.25rem !important;
  color: var(--texto);
  background: radial-gradient(900px 380px at 50% -80px, var(--halo), transparent 70%), var(--app-bg) !important; }

/* ---------- animações ---------- */
@keyframes subir { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes entrar { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
#app { animation: entrar .4s ease-out both; }
#chat [data-testid="user"], #chat [data-testid="bot"], #chat .message-row { animation: subir .3s ease-out both; }

/* ---------- cabeçalho ---------- */
#topo { align-items: center; gap: 1rem; }
#cabecalho h1 { font-size: 1.5rem; font-weight: 650; letter-spacing: -.01em; margin: 0; color: var(--texto); }
#cabecalho h1::before { content: ""; display: inline-block; width: .62em; height: .62em; border-radius: .18em;
  margin-right: .55rem; background: linear-gradient(135deg, var(--acento), var(--acento-2));
  box-shadow: 0 4px 14px var(--halo); }
#cabecalho p { margin: .25rem 0 0; color: var(--texto-suave); }
#aviso { background: var(--surface-2); border: 1px solid var(--borda); border-radius: 12px;
         padding: .5rem .9rem; font-size: .82rem; color: var(--texto-suave); }

/* seletor de tema compacto */
#tema { min-width: 0 !important; }
#tema .wrap, #tema fieldset { gap: .3rem; flex-wrap: nowrap; justify-content: flex-end; }
#tema label { padding: .22rem .7rem !important; font-size: .76rem !important; border-radius: 999px !important;
  background: var(--surface) !important; border: 1px solid var(--borda) !important; color: var(--texto-suave) !important;
  box-shadow: none !important; cursor: pointer; transition: border-color .15s, box-shadow .15s, background .15s; }
#tema label:hover { border-color: var(--acento) !important; }
#tema label.selected { background: var(--acento) !important; border-color: var(--acento) !important;
  color: #fff !important; box-shadow: 0 4px 14px var(--sombra) !important; }
#tema input { display: none !important; }

/* ---------- cartões ---------- */
#lateral { background: var(--surface); border: 1px solid var(--borda); border-radius: 16px; padding: 1rem; gap: .7rem;
  box-shadow: 0 1px 2px var(--sombra-suave), 0 10px 30px var(--sombra-suave);
  height: calc(100vh - 330px); min-height: 420px; overflow-y: auto; overflow-x: hidden;
  scrollbar-width: thin; scrollbar-color: var(--borda) transparent; }
#lateral h4 { margin: 0; font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; color: var(--texto-suave); }
#chat { background: var(--surface) !important; border: 1px solid var(--borda) !important; border-radius: 16px !important;
  box-shadow: 0 1px 2px var(--sombra-suave), 0 10px 30px var(--sombra-suave) !important; }
/* mensagens: usuário em balão de cor, assistente em texto limpo, sem faixa de fundo */
#chat .message, #chat [data-testid="bot"], #chat [data-testid="user"] { font-size: .97rem; line-height: 1.6; box-shadow: none; }
#chat [data-testid="user"], #chat .message.user {
  background: linear-gradient(135deg, #4f46e5, #6d5ae8) !important; color: #fff !important; border: none !important;
  border-radius: 18px 18px 4px 18px !important; padding: .6rem 1rem !important; max-width: 78%; }
#chat [data-testid="user"] *, #chat .message.user * { color: #fff !important; }
#chat [data-testid="bot"], #chat .message.bot {
  background: transparent !important; border: none !important; padding: .15rem .25rem !important; max-width: 100%; }
#chat .message p { margin: .35rem 0; }
#chat .message blockquote { margin: .6rem 0 .3rem; padding: .45rem .8rem; border: 1px solid var(--borda);
  border-left: 3px solid var(--acento); border-radius: 10px; background: var(--surface-2);
  color: var(--texto-suave); font-size: .86rem; line-height: 1.5; }
#chat .message blockquote strong { color: var(--texto); }
#chat .message em { color: var(--texto-suave); font-size: .8rem; }

/* mensagem inicial centralizada, com respiro */
#chat [class*="placeholder"] { display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; height: 100%; padding: 2.5rem 3rem; gap: .35rem; }
#chat [class*="placeholder"] h3 { font-size: 1.35rem; margin: 0 0 .4rem; color: var(--texto); }
#chat [class*="placeholder"] p { color: var(--texto-suave); max-width: 34rem; margin: .2rem 0; }

/* ---------- sugestões ---------- */
#chips { gap: .5rem; }
#chips button { width: 100%; background: var(--surface-2); border: 1px solid var(--borda); color: var(--texto);
  border-radius: 12px; font-weight: 400; font-size: .85rem; line-height: 1.35; white-space: normal; text-align: left;
  padding: .55rem .7rem; box-sizing: border-box; max-width: 100%;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
#chips button:hover { transform: translateY(-2px); border-color: var(--acento); box-shadow: 0 8px 20px var(--sombra); }
#chips button:active { transform: translateY(0) scale(.985); box-shadow: 0 2px 6px var(--sombra); }

/* ---------- barra de entrada ---------- */
#entrada { align-items: center; gap: .5rem; padding: .35rem .45rem .35rem .9rem; border-radius: 16px;
  border: 1px solid var(--borda); background: var(--surface);
  box-shadow: 0 1px 2px var(--sombra-suave), 0 10px 30px var(--sombra-suave);
  transition: border-color .15s ease, box-shadow .15s ease; }
#entrada:focus-within { border-color: var(--acento); box-shadow: 0 0 0 4px var(--halo), 0 10px 30px var(--sombra-suave); }
#entrada textarea { font-size: 1rem; background: transparent !important; }
#entrada button { border-radius: 12px; border: none !important;
  background: linear-gradient(135deg, var(--acento), var(--acento-2)) !important; color: #fff !important;
  transition: transform .15s ease, box-shadow .15s ease; }
#entrada button:hover { transform: translateY(-1px); box-shadow: 0 8px 20px var(--halo), 0 4px 12px var(--sombra); }
#entrada button:active { transform: translateY(0) scale(.97); }

/* ---------- detalhes ---------- */
button:focus-visible, label:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
#status, #rodape { font-size: .8rem; color: var(--texto-suave); }
#rodape { text-align: center; }
#lateral, #chat, #chat * { scrollbar-width: thin; scrollbar-color: var(--borda) transparent; }
#lateral::-webkit-scrollbar, #chat *::-webkit-scrollbar { width: 6px; height: 6px; }
#lateral::-webkit-scrollbar-track, #chat *::-webkit-scrollbar-track, #lateral::-webkit-scrollbar-corner { background: transparent; }
#lateral::-webkit-scrollbar-thumb, #chat *::-webkit-scrollbar-thumb { background: var(--borda); border-radius: 8px; }
#lateral::-webkit-scrollbar-thumb:hover, #chat *::-webkit-scrollbar-thumb:hover { background: var(--texto-suave); }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""

JS_APLICAR_TEMA = """(t) => {
  const escuro = t === 'Escuro' || (t === 'Automático' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.body.classList.toggle('dark', escuro);
  try { localStorage.setItem('tema_demo', t); } catch (e) {}
  return t;
}"""

JS_CARREGAR_TEMA = """() => {
  let t = 'Automático';
  try { t = localStorage.getItem('tema_demo') || t; } catch (e) {}
  const escuro = t === 'Escuro' || (t === 'Automático' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.body.classList.toggle('dark', escuro);
  return t;
}"""


def opcoes_launch() -> dict:
    """Argumentos de `demo.launch()` com o visual (tema e CSS)."""
    return {"theme": gr.themes.Soft(primary_hue="indigo", neutral_hue="slate", radius_size="lg",
                                    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]),
            "css": CSS}


def construir_demo(servico: ServicoDemo, cfg: ConfigDemo) -> gr.Blocks:
    sal = cfg.sal.get_secret_value()
    perguntas = carregar_perguntas()
    iniciais = sugestoes_iniciais(perguntas, N_CHIPS)

    def visitante(request: gr.Request | None) -> str:
        host = request.client.host if request is not None and request.client else None
        cab = dict(request.headers) if request is not None and request.headers else {}
        return id_visitante(extrair_ip(cab, host), sal)

    def chips(textos: list[str]) -> list[gr.Button]:
        return [gr.Button(value=textos[i], visible=True, interactive=True) if i < len(textos)
                else gr.Button(visible=False) for i in range(N_CHIPS)]

    def saida(turno: Turno) -> tuple:
        return (turno.historico, gr.Textbox(value="", interactive=True), *chips(turno.sugestoes),
                gr.File(value=turno.arquivos or None, visible=bool(turno.arquivos)), turno.status)

    def enviar(texto: str | None, historico: list | None, request: gr.Request):
        pergunta = (texto or "").strip()
        if not pergunta:
            yield (historico or [], gr.Textbox(), *[gr.Button() for _ in range(N_CHIPS)], gr.File(), gr.Markdown())
            return
        # 1) mostra a pergunta e o aviso de espera, travando a entrada para evitar envio duplo
        yield (iniciar_turno(historico, pergunta), gr.Textbox(value="", interactive=False),
               *[gr.Button(interactive=False) for _ in range(N_CHIPS)], gr.File(visible=False), gr.Markdown())
        # 2) resposta final
        yield saida(concluir_turno(servico, pergunta, visitante(request), historico, perguntas,
                                   por_visitante=cfg.por_visitante_dia, n_iniciais=N_CHIPS))

    def limpar():
        return ([], gr.Textbox(value="", interactive=True), *chips(iniciais), gr.File(value=None, visible=False))

    def ao_abrir(request: gr.Request):
        return status_restantes(servico.restantes(visitante(request)), cfg.por_visitante_dia)

    with gr.Blocks(title="Busca em políticas de auditoria (demo)") as demo:
        with gr.Column(elem_id="app"):
            with gr.Row(elem_id="topo"):
                gr.Markdown("# Busca em políticas de auditoria\n"
                            "Respostas sobre as políticas da Gutenberg Systems, sempre com a fonte citada.",
                            elem_id="cabecalho", scale=4)
                tema = gr.Radio(["Automático", "Claro", "Escuro"], value="Automático", show_label=False,
                                container=False, scale=1, min_width=260, elem_id="tema")
            gr.Markdown(AVISO, elem_id="aviso")
            with gr.Row(equal_height=False):
                with gr.Column(scale=1, min_width=280, elem_id="lateral"):
                    gr.Markdown("#### Sugestões")
                    with gr.Column(elem_id="chips"):
                        botoes_chips = [gr.Button(value=iniciais[i] if i < len(iniciais) else "", variant="secondary",
                                                  visible=i < len(iniciais)) for i in range(N_CHIPS)]
                    arquivos = gr.File(label="Documentos citados (baixar)", visible=False, interactive=False,
                                       file_count="multiple", height=120)
                    status = gr.Markdown(elem_id="status")
                    limpar_btn = gr.Button("Nova conversa", size="sm", variant="secondary")
                    with gr.Accordion("Base de documentos (fictícios)", open=False):
                        gr.File(value=[str(p) for p in sorted(DIR_DOCS.glob("POL-*.md"))], interactive=False,
                                file_count="multiple", show_label=False, height=200)
                with gr.Column(scale=3, min_width=480):
                    chatbot = gr.Chatbot(
                        value=[], height="calc(100vh - 330px)", layout="bubble", show_label=False,
                        buttons=["copy", "copy_all"], elem_id="chat",
                        placeholder="### Como posso ajudar?\n\n"
                                    "Pergunte sobre controle de acesso, conciliação de pagamentos, gestão de mudanças, "
                                    "incidentes, backup, fornecedores, logs, classificação de dados ou segregação de "
                                    "funções.\n\nEscolha uma sugestão ao lado ou escreva sua pergunta.")
                    with gr.Row(elem_id="entrada"):
                        entrada = gr.Textbox(show_label=False, container=False, lines=1, max_lines=4, scale=8,
                                             max_length=cfg.max_chars, autofocus=True,
                                             placeholder="Escreva sua pergunta e tecle Enter")
                        botao = gr.Button("Enviar", variant="primary", scale=1, min_width=96)
            gr.Markdown(f"Cada pergunta é independente (sem memória da conversa) · {cfg.por_visitante_dia} perguntas "
                        "por visitante por dia; respostas repetidas vêm do cache e não contam · "
                        "Modelos: OpenAI e Anthropic (o mais barato responde primeiro).", elem_id="rodape")

        saidas = [chatbot, entrada, *botoes_chips, arquivos, status]
        entrada.submit(enviar, [entrada, chatbot], saidas, concurrency_limit=4)
        botao.click(enviar, [entrada, chatbot], saidas, concurrency_limit=4)
        for chip in botoes_chips:
            chip.click(enviar, [chip, chatbot], saidas, concurrency_limit=4)
        limpar_btn.click(limpar, None, [chatbot, entrada, *botoes_chips, arquivos])
        tema.change(None, tema, None, js=JS_APLICAR_TEMA)
        demo.load(ao_abrir, None, status)
        demo.load(None, None, tema, js=JS_CARREGAR_TEMA)
    return demo
