# Publicar a demo no Hugging Face Spaces (passo a passo)

O Hugging Face é só a **hospedagem**. Os modelos continuam sendo OpenAI e Anthropic.
Todos os comandos abaixo são para o terminal do VS Code, dentro da pasta `repo_bloco2`, com o `.venv` ativado
(o prompt começa com `(.venv)`).

## Parte A. Preparar o projeto no seu computador

**A1. Descobrir a versão do Python e do Gradio.**
```
python --version
pip install gradio==6.30.0
python -c "import gradio; print(gradio.__version__)"
```
Anote os dois resultados (por exemplo, Python 3.11.9 e Gradio 6.30.0). Se o `pip` instalar outra versão do Gradio,
use a que ele instalou nos passos A2 e A3.

**A2. Conferir o `README.md`.** Abra o arquivo. O bloco entre os dois `---` do topo é a configuração do Space:
```
sdk_version: 6.30.0        <- igual à versão do Gradio do passo A1
python_version: "3.11"     <- 3.11 ou 3.12, igual à do passo A1 (só os dois primeiros números)
```
Não apague esse bloco nem mude `app_file: app.py`.

**A3. Conferir o `requirements.txt`.** Precisa conter a linha `gradio==6.30.0` (ou a versão do passo A1).
Sem ela o Space não instala o Gradio e o build falha.

**A4. Testar local.** `python app.py`, abra http://127.0.0.1:7860, faça uma pergunta do gabarito, repita-a
(deve aparecer "resposta em cache (sem custo)") e esgote as 5 perguntas do dia.

**A5. Salvar no GitHub antes de publicar.** O envio ao Space leva só o que foi commitado.
```
git add .
git status
```
Confira que `.env`, `logs/` e `indice/` **não** aparecem na lista. Depois:
```
git commit -m "Bloco 7: demo Gradio"
git push
git ls-files .env logs indice
```
O último comando deve imprimir **nada**.

## Parte B. Limite de gasto fora do código (obrigatório)

O teto do código (`BUDGET_*_USD`) e os contadores da demo ficam em arquivos que **somem quando o Space reinicia**
(disco efêmero, salvo armazenamento persistente pago; confirme na documentação do Spaces). Por isso, configure um limite
de gasto na própria conta de cada provedor:
- **OpenAI**: no painel da conta, procure "Billing" e "Limits" (limite mensal de gasto).
- **Anthropic**: no Console, procure "Settings" e "Limits" (limite mensal de gasto).
Os nomes dos menus mudam com o tempo; o que importa é definir um **limite mensal baixo** (sugestão: US$ 2 em cada).

## Parte C. Criar o Space

**C1. Conta e token.** Crie conta em huggingface.co. Em Settings → Access Tokens, crie um token com
**permissão de escrita (write)** e copie-o para um lugar seguro. Ele será a "senha" do `git push`. Não cole o token em chats.

**C2. Novo Space.** No site: New → Space. Preencha:
- Space name: por exemplo, `busca-politicas-auditoria`
- SDK: **Gradio**
- Hardware: **CPU basic** (gratuito)
- Visibility: **Public**
O endereço será `https://huggingface.co/spaces/SEU_USUARIO/busca-politicas-auditoria`.

**C3. Secrets e variáveis.** No Space: Settings → Variables and secrets.
| Tipo | Nome | Valor |
|---|---|---|
| Secret | `OPENAI_API_KEY` | sua chave da OpenAI |
| Secret | `ANTHROPIC_API_KEY` | sua chave da Anthropic |
| Secret | `DEMO_SALT` | texto longo e aleatório (anonimiza os visitantes) |
| Variable | `BUDGET_OPENAI_USD` | `0.5` |
| Variable | `BUDGET_ANTHROPIC_USD` | `0.5` |
| Variable | `DEMO_TETO_CUSTO_DIA_USD` | `0.25` |
Chaves entram **só como Secret**. Variables são visíveis publicamente.

## Parte D. Enviar o código e conferir

**D1. Enviar.** No terminal (troque SEU_USUARIO e o nome do Space):
```
git remote add space https://huggingface.co/spaces/SEU_USUARIO/busca-politicas-auditoria
git push --force space main
```
Quando pedir usuário e senha: usuário = seu usuário do Hugging Face; senha = o **token** do passo C1.
O `--force` é necessário só na primeira vez, porque o Space nasce com arquivos iniciais que serão substituídos.

**D2. Acompanhar o build.** Na página do Space, veja o status ("Building" → "Running") e a aba **Logs**.
Leva alguns minutos. Na primeira partida o índice é criado sozinho (custo de embeddings abaixo de US$ 0,001).

**D3. Verificar (critério de pronto).** Abra o link do Space numa **janela anônima** (sem login no Hugging Face):
1. a demo abre sem instalar nada;
2. uma pergunta do gabarito responde com fonte citada;
3. a mesma pergunta de novo mostra "resposta em cache (sem custo)";
4. depois de 5 perguntas diferentes, aparece a mensagem de limite.

## Atualizar depois
Depois de mudar o código: `git add .`, `git commit -m "..."`, `git push` (GitHub) e `git push space main` (Space).
O `--force` não é mais necessário.

## Problemas comuns
| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Build falha com "No matching distribution" | versão do Python ou de pacote incompatível | ajuste `python_version` no `README.md`; confira `requirements.txt` |
| "Runtime error" e nos Logs "Variável de ambiente OPENAI_API_KEY não definida" | secret ausente ou com nome diferente | recrie o Secret com o nome exato e reinicie o Space (Settings → Restart) |
| Erro de autenticação no `git push` | token errado ou sem permissão de escrita | crie um token write novo e tente de novo |
| `src/...: ModuleNotFoundError: gradio` | `gradio` ausente do `requirements.txt` | adicione a linha e faça commit e push de novo |
| Demo responde "limite" logo de início | contadores de outro dia/visitante | normal: o limite é por visitante por dia (fuso de Brasília) |
