# Gerenciador de Contas (bot pessoal)

Bot de Telegram pra organizar as contas de streaming que você
cria (Netflix, Disney+, etc.) — cadastro completo + lembrete
automático de verificação.

## Arquivos
- `config.py` — variáveis de ambiente
- `database.py` — banco SQLite (tabela `contas`)
- `main.py` — bot em si
- `requirements.txt` — dependência (python-telegram-bot)

## Como colocar no ar (Railway)

1. Crie um repositório novo no GitHub com esses 4 arquivos.
2. No Railway, crie um projeto novo → "Deploy from GitHub repo"
   → selecione esse repositório.
3. Em **Variables**, adicione:
   - `BOT_TOKEN` — o token do bot (peça pro @BotFather criar um
     bot novo com `/newbot`, diferente do PLAYER STORE)
   - `ADMIN_ID` — o seu ID numérico do Telegram (fale com
     @userinfobot pra descobrir)
4. Deploy automático. Depois é só mandar `/start` no bot novo.

## Como usar

- **➕ Nova Conta** — cadastro passo a passo (serviço, email,
  senha, data de criação, custo, fornecedor, telas/perfis,
  observações). Pode pular qualquer campo digitando `pular`.
- **📋 Listar Contas** — lista paginada de tudo, toque numa
  conta pra ver detalhes/editar/excluir/marcar como verificada.
- **🔍 Buscar** — procura por serviço, email ou fornecedor.
- **⚙️ Intervalo de Verificação** — de quanto em quanto tempo
  (em dias) você quer ser lembrado de checar se cada conta
  ainda está ativa. Padrão: 30 dias.

O bot roda uma checagem a cada 6 horas e te avisa (nesse
mesmo chat) quando alguma conta passar do intervalo definido
sem ser marcada como verificada.

Esse bot é de uso pessoal — só o `ADMIN_ID` cadastrado consegue
usá-lo; qualquer outra pessoa recebe "acesso negado".
