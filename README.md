# Gerenciador de Contas (bot pessoal)

Bot de Telegram pra organizar as contas de streaming que vocÃª
cria (Netflix, Disney+, etc.) â€” cadastro completo + lembrete
automÃ¡tico de verificaÃ§Ã£o.

## Arquivos
- `config.py` â€” variÃ¡veis de ambiente
- `database.py` â€” banco SQLite (tabela `contas`)
- `main.py` â€” bot em si
- `requirements.txt` â€” dependÃªncia (python-telegram-bot)

## Como colocar no ar (Railway)

1. Crie um repositÃ³rio novo no GitHub com esses 4 arquivos.
2. No Railway, crie um projeto novo â†’ "Deploy from GitHub repo"
   â†’ selecione esse repositÃ³rio.
3. Em **Variables**, adicione:
   - `BOT_TOKEN` â€” o token do bot (peÃ§a pro @BotFather criar um
     bot novo com `/newbot`, diferente do PLAYER STORE)
   - `ADMIN_ID` â€” o seu ID numÃ©rico do Telegram (fale com
     @userinfobot pra descobrir)
4. Deploy automÃ¡tico. Depois Ã© sÃ³ mandar `/start` no bot novo.

## Como usar

- **âž• Nova Conta** â€” cadastro passo a passo (serviÃ§o, email,
  senha, data de criaÃ§Ã£o, custo, fornecedor, telas/perfis,
  observaÃ§Ãµes, tags). Pode pular qualquer campo digitando
  `pular`.
- **ðŸ“‹ Listar Contas** â€” lista paginada de tudo, toque numa
  conta pra ver detalhes/editar/excluir/marcar como verificada.
- **ðŸ”½ Filtrar Contas** â€” filtra a listagem por serviÃ§o (sÃ³
  Netflix, sÃ³ Disney+...), por status (sÃ³ ativas/inativas) ou
  por tag. O filtro fica ativo atÃ© vocÃª limpar ou sair pro
  menu principal.
- **â˜‘ï¸ VerificaÃ§Ã£o em Lote** â€” marque vÃ¡rias contas ativas de
  uma vez (toque pra selecionar) e confirme como "âœ… OK" ou
  "âš ï¸ Com problema" pra todas juntas.
- **ðŸ” Buscar** â€” procura por serviÃ§o, email, fornecedor ou tag.
- **ðŸ’° Resumo de Custos** â€” total investido na criaÃ§Ã£o das
  contas (soma de todos os `custo_criacao`), separado por
  ativas/inativas.
- **âš™ï¸ Intervalo de VerificaÃ§Ã£o** â€” de quanto em quanto tempo
  (em dias) vocÃª quer ser lembrado de checar se cada conta
  ainda estÃ¡ ativa. PadrÃ£o: 30 dias.

### Nos detalhes de cada conta

- **ðŸ·ï¸ Tags** â€” marque contas com etiquetas livres tipo `vip`,
  `problema`, `revisar` (separadas por vÃ­rgula). EditÃ¡vel como
  qualquer outro campo, e usada nos filtros e na busca.
- **ðŸ‘ï¸ Mostrar Senha** â€” a senha fica oculta (`â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢`) por
  padrÃ£o na tela de detalhes; toque no botÃ£o pra ver o valor
  real num alerta rÃ¡pido.
- **âœ… Marcar como Verificada** â€” agora pede o resultado da
  checagem: "âœ… OK" ou "âš ï¸ Com problema". Cada verificaÃ§Ã£o fica
  registrada no histÃ³rico da conta.
- **ðŸ“œ HistÃ³rico de VerificaÃ§Ãµes** â€” mostra as Ãºltimas 10
  verificaÃ§Ãµes da conta, com data e resultado.

O bot roda uma checagem a cada 6 horas e te avisa (nesse
mesmo chat) quando alguma conta passar do intervalo definido
sem ser marcada como verificada â€” com botÃµes de "âœ… OK" e
"âš ï¸ Problema" direto na notificaÃ§Ã£o.

Esse bot Ã© de uso pessoal â€” sÃ³ o `ADMIN_ID` cadastrado consegue
usÃ¡-lo; qualquer outra pessoa recebe "acesso negado".
