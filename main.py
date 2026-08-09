import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    verificar_configuracao,
)

from database import (
    criar_tabelas,
    cadastrar_conta,
    listar_contas,
    buscar_conta,
    buscar_contas_por_termo,
    atualizar_campo_conta,
    definir_status_conta,
    marcar_conta_verificada,
    excluir_conta,
    listar_contas_para_verificar,
    contar_contas,
    definir_configuracao,
    obter_configuracao,
)


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

INTERVALO_PADRAO_DIAS = 30
INTERVALO_CHECAGEM_LOOP = 6 * 60 * 60  # a cada 6h
VERIFICADOR_TASK = "verificador_contas_task"

CAMPOS_CADASTRO = [
    ("servico", "📺 Serviço (ex: Netflix, Disney+)"),
    ("email", "📧 Email/login"),
    ("senha", "🔑 Senha"),
    ("data_criacao", "🗓️ Data de criação (ex: 08/08/2026, ou envie \"pular\")"),
    ("custo_criacao", "💰 Custo de criação (ex: 15.00, ou envie \"pular\")"),
    ("fornecedor", "🏷️ Fornecedor/origem (ou envie \"pular\")"),
    ("telas_perfis", "🖥️ Telas/perfis já usados (ou envie \"pular\")"),
    ("observacoes", "📝 Observações gerais (ou envie \"pular\")"),
]


def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except (ValueError, TypeError):
        return False


# =========================================================
# START / MENU
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        if update.message:
            await update.message.reply_text(
                "❌ Este bot é de uso pessoal."
            )
        return

    context.user_data.clear()

    total, ativas = contar_contas()

    texto = (
        "🗂️ *GERENCIADOR DE CONTAS*\n\n"
        f"📦 Total cadastradas: {total}\n"
        f"✅ Ativas: {ativas}\n\n"
        "Escolha uma opção:"
    )

    if update.message:
        await update.message.reply_text(
            texto,
            reply_markup=menu_principal(),
            parse_mode="Markdown",
        )


def menu_principal():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ NOVA CONTA",
                    callback_data="nova_conta",
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 LISTAR CONTAS",
                    callback_data="listar_1",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔍 BUSCAR",
                    callback_data="buscar",
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ INTERVALO DE VERIFICAÇÃO",
                    callback_data="config_intervalo",
                )
            ],
        ]
    )


# =========================================================
# NOVA CONTA (FLUXO SEQUENCIAL)
# =========================================================

async def iniciar_nova_conta(
    query,
    context,
):
    context.user_data.clear()
    context.user_data["cadastro_dados"] = {}
    context.user_data["cadastro_passo"] = 0

    campo, pergunta = CAMPOS_CADASTRO[0]

    await query.edit_message_text(
        "➕ *NOVA CONTA*\n\n"
        f"{pergunta}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ CANCELAR",
                        callback_data="cancelar_cadastro",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def processar_passo_cadastro(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if "cadastro_passo" not in context.user_data:
        return False

    if not update.message or not update.message.text:
        return True

    passo = context.user_data["cadastro_passo"]
    campo, _ = CAMPOS_CADASTRO[passo]

    texto = update.message.text.strip()

    if texto.lower() == "pular":
        valor = None
    elif campo == "custo_criacao":
        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "❌ Digite um número válido "
                "(ex: 15.00) ou \"pular\"."
            )
            return True
    else:
        valor = texto

    context.user_data["cadastro_dados"][campo] = valor

    proximo_passo = passo + 1

    if proximo_passo < len(CAMPOS_CADASTRO):

        context.user_data["cadastro_passo"] = proximo_passo

        _, pergunta = CAMPOS_CADASTRO[proximo_passo]

        await update.message.reply_text(
            pergunta,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "❌ CANCELAR",
                            callback_data="cancelar_cadastro",
                        )
                    ]
                ]
            ),
        )
        return True

    # Último passo: salva no banco.
    dados = context.user_data["cadastro_dados"]

    conta_id = cadastrar_conta(
        servico=dados.get("servico") or "Sem nome",
        email=dados.get("email"),
        senha=dados.get("senha"),
        data_criacao=dados.get("data_criacao"),
        custo_criacao=dados.get("custo_criacao"),
        fornecedor=dados.get("fornecedor"),
        telas_perfis=dados.get("telas_perfis"),
        observacoes=dados.get("observacoes"),
    )

    context.user_data.clear()

    await update.message.reply_text(
        "✅ *CONTA CADASTRADA!*\n\n"
        f"🆔 ID: `{conta_id}`\n"
        f"📺 Serviço: {dados.get('servico')}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📦 Ver conta",
                        callback_data=f"conta_{conta_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 Menu",
                        callback_data="menu",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# LISTAR CONTAS (COM PAGINAÇÃO SIMPLES)
# =========================================================

CONTAS_POR_PAGINA = 8


async def mostrar_lista_contas(
    query,
    pagina=1,
):
    contas = listar_contas()

    if not contas:
        await query.edit_message_text(
            "📋 *LISTAR CONTAS*\n\n"
            "Nenhuma conta cadastrada ainda.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Nova conta",
                            callback_data="nova_conta",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    total_paginas = (
        len(contas) + CONTAS_POR_PAGINA - 1
    ) // CONTAS_POR_PAGINA

    pagina = max(1, min(pagina, total_paginas))

    inicio = (pagina - 1) * CONTAS_POR_PAGINA
    fim = inicio + CONTAS_POR_PAGINA

    botoes = []

    for conta in contas[inicio:fim]:

        conta_id, servico, email, status = conta

        emoji_status = (
            "✅" if status == "ativa" else "⚫"
        )

        rotulo = f"{emoji_status} {servico}"

        if email:
            rotulo += f" ({email[:20]})"

        botoes.append(
            [
                InlineKeyboardButton(
                    rotulo[:60],
                    callback_data=f"conta_{conta_id}",
                )
            ]
        )

    navegacao = []

    if pagina > 1:
        navegacao.append(
            InlineKeyboardButton(
                "⬅️",
                callback_data=f"listar_{pagina - 1}",
            )
        )

    if pagina < total_paginas:
        navegacao.append(
            InlineKeyboardButton(
                "➡️",
                callback_data=f"listar_{pagina + 1}",
            )
        )

    if navegacao:
        botoes.append(navegacao)

    botoes.append(
        [
            InlineKeyboardButton(
                "🏠 Menu",
                callback_data="menu",
            )
        ]
    )

    await query.edit_message_text(
        "📋 *LISTAR CONTAS*\n\n"
        f"Página {pagina}/{total_paginas} — "
        f"{len(contas)} conta(s) no total:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# DETALHES DA CONTA
# =========================================================

async def mostrar_detalhes_conta(
    query,
    conta_id,
):
    conta = buscar_conta(conta_id)

    if not conta:
        await query.answer(
            "❌ Conta não encontrada.",
            show_alert=True,
        )
        return

    (
        _,
        servico,
        email,
        senha,
        data_criacao,
        custo_criacao,
        fornecedor,
        telas_perfis,
        observacoes,
        status,
        ultima_verificacao,
        criado_em,
    ) = conta

    emoji_status = (
        "✅ Ativa" if status == "ativa" else "⚫ Inativa"
    )

    texto = (
        f"📦 *{servico}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📧 Email: {email or '—'}\n"
        f"🔑 Senha: `{senha or '—'}`\n"
        f"🗓️ Criada em: {data_criacao or '—'}\n"
        f"💰 Custo: "
        f"{f'R$ {custo_criacao:.2f}' if custo_criacao else '—'}\n"
        f"🏷️ Fornecedor: {fornecedor or '—'}\n"
        f"🖥️ Telas/perfis: {telas_perfis or '—'}\n"
        f"📝 Obs: {observacoes or '—'}\n"
        f"📊 Status: {emoji_status}\n"
        f"🔎 Última verificação: "
        f"{str(ultima_verificacao)[:16]}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    botoes = [
        [
            InlineKeyboardButton(
                "✅ MARCAR COMO VERIFICADA",
                callback_data=f"verificar_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ EDITAR",
                callback_data=f"editar_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                (
                    "⚫ MARCAR INATIVA"
                    if status == "ativa"
                    else "✅ MARCAR ATIVA"
                ),
                callback_data=f"toggle_status_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ EXCLUIR",
                callback_data=f"excluir_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Menu",
                callback_data="menu",
            )
        ],
    ]

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# EDITAR CAMPO
# =========================================================

NOMES_CAMPOS = {
    "servico": "Serviço",
    "email": "Email/login",
    "senha": "Senha",
    "data_criacao": "Data de criação",
    "custo_criacao": "Custo de criação",
    "fornecedor": "Fornecedor",
    "telas_perfis": "Telas/perfis",
    "observacoes": "Observações",
}


async def mostrar_menu_editar(
    query,
    conta_id,
):
    botoes = []

    for campo, nome in NOMES_CAMPOS.items():
        botoes.append(
            [
                InlineKeyboardButton(
                    f"✏️ {nome}",
                    callback_data=(
                        f"editarcampo_{conta_id}_{campo}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "⬅️ Voltar",
                callback_data=f"conta_{conta_id}",
            )
        ]
    )

    await query.edit_message_text(
        "✏️ *EDITAR CONTA*\n\n"
        "Qual campo você quer alterar?",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def iniciar_edicao_campo(
    query,
    context,
    conta_id,
    campo,
):
    context.user_data.clear()
    context.user_data["editando_conta_id"] = conta_id
    context.user_data["editando_campo"] = campo

    nome_campo = NOMES_CAMPOS.get(campo, campo)

    await query.edit_message_text(
        f"✏️ *EDITAR {nome_campo.upper()}*\n\n"
        "Digite o novo valor:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data=f"conta_{conta_id}",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def processar_edicao_campo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if "editando_campo" not in context.user_data:
        return False

    if not update.message or not update.message.text:
        return True

    conta_id = context.user_data["editando_conta_id"]
    campo = context.user_data["editando_campo"]

    texto = update.message.text.strip()

    if campo == "custo_criacao":
        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "❌ Digite um número válido "
                "(ex: 15.00)."
            )
            return True
    else:
        valor = texto

    atualizar_campo_conta(
        conta_id,
        campo,
        valor,
    )

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Campo atualizado!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📦 Ver conta",
                        callback_data=f"conta_{conta_id}",
                    )
                ]
            ]
        ),
    )

    return True


# =========================================================
# BUSCAR
# =========================================================

async def iniciar_busca(
    query,
    context,
):
    context.user_data.clear()
    context.user_data["aguardando_busca"] = True

    await query.edit_message_text(
        "🔍 *BUSCAR CONTA*\n\n"
        "Digite o serviço, email ou fornecedor "
        "que você está procurando.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def processar_busca(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.user_data.get("aguardando_busca"):
        return False

    if not update.message or not update.message.text:
        return True

    termo = update.message.text.strip()

    context.user_data.clear()

    resultados = buscar_contas_por_termo(termo)

    if not resultados:
        await update.message.reply_text(
            f"❌ Nenhum resultado para \"{termo}\".",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ]
                ]
            ),
        )
        return True

    botoes = []

    for conta in resultados[:20]:

        conta_id, servico, email, status = conta

        emoji_status = (
            "✅" if status == "ativa" else "⚫"
        )

        rotulo = f"{emoji_status} {servico}"

        if email:
            rotulo += f" ({email[:20]})"

        botoes.append(
            [
                InlineKeyboardButton(
                    rotulo[:60],
                    callback_data=f"conta_{conta_id}",
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "🏠 Menu",
                callback_data="menu",
            )
        ]
    )

    await update.message.reply_text(
        f"🔍 *RESULTADOS PARA* \"{termo}\":",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# CONFIGURAR INTERVALO DE VERIFICAÇÃO
# =========================================================

async def iniciar_config_intervalo(
    query,
    context,
):
    context.user_data.clear()
    context.user_data["aguardando_intervalo"] = True

    atual = (
        obter_configuracao("intervalo_dias")
        or str(INTERVALO_PADRAO_DIAS)
    )

    await query.edit_message_text(
        "⚙️ *INTERVALO DE VERIFICAÇÃO*\n\n"
        f"📋 Valor atual: {atual} dias\n\n"
        "Digite de quantos em quantos dias "
        "você quer ser lembrado de verificar "
        "cada conta.\n\n"
        "Exemplo:\n"
        "`30`\n"
        "`15`",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def processar_config_intervalo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.user_data.get("aguardando_intervalo"):
        return False

    if not update.message or not update.message.text:
        return True

    texto = update.message.text.strip()

    if not texto.isdigit() or int(texto) <= 0:
        await update.message.reply_text(
            "❌ Digite um número inteiro maior "
            "que zero."
        )
        return True

    definir_configuracao(
        "intervalo_dias",
        texto,
    )

    context.user_data.clear()

    await update.message.reply_text(
        "✅ *INTERVALO ATUALIZADO!*\n\n"
        f"⚙️ Novo valor: {texto} dias",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🏠 Menu",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# VERIFICADOR AUTOMÁTICO (LOOP EM BACKGROUND)
# =========================================================

async def checar_contas_pendentes(
    bot,
):
    try:
        intervalo = int(
            obter_configuracao("intervalo_dias")
            or INTERVALO_PADRAO_DIAS
        )

        pendentes = listar_contas_para_verificar(
            intervalo
        )

        if not pendentes:
            return

        texto = (
            "🔔 *CONTAS PRA VERIFICAR*\n\n"
            f"As contas abaixo não são checadas "
            f"há {intervalo}+ dias:\n\n"
        )

        botoes = []

        for conta in pendentes[:15]:

            conta_id, servico, email, _ = conta

            rotulo = f"{servico}"

            if email:
                rotulo += f" ({email[:20]})"

            texto += f"📦 {rotulo}\n"

            botoes.append(
                [
                    InlineKeyboardButton(
                        f"✅ Verificada: {servico[:25]}",
                        callback_data=(
                            f"verificar_{conta_id}"
                        ),
                    )
                ]
            )

        await bot.send_message(
            chat_id=ADMIN_ID,
            text=texto,
            reply_markup=InlineKeyboardMarkup(
                botoes
            ),
            parse_mode="Markdown",
        )

    except Exception as erro:
        print(
            "ERRO NO VERIFICADOR DE CONTAS:",
            repr(erro),
        )


async def loop_verificador(
    application: Application,
):
    print(
        "🔔 Verificador de contas iniciado."
    )

    while True:
        try:
            await checar_contas_pendentes(
                application.bot
            )

        except asyncio.CancelledError:
            print(
                "🔔 Verificador de contas encerrado."
            )
            raise

        except Exception as erro:
            print(
                "ERRO NO LOOP DO VERIFICADOR:",
                repr(erro),
            )

        await asyncio.sleep(
            INTERVALO_CHECAGEM_LOOP
        )


async def iniciar_verificador(
    application: Application,
):
    try:
        await application.bot.set_my_commands(
            [
                BotCommand(
                    "start",
                    "Abrir menu principal",
                ),
                BotCommand(
                    "nova",
                    "Cadastrar nova conta",
                ),
                BotCommand(
                    "listar",
                    "Listar contas",
                ),
                BotCommand(
                    "buscar",
                    "Buscar conta",
                ),
            ]
        )
    except Exception as erro:
        print(
            "ERRO AO REGISTRAR COMANDOS:",
            repr(erro),
        )

    task = asyncio.create_task(
        loop_verificador(application),
        name=VERIFICADOR_TASK,
    )

    application.bot_data[
        VERIFICADOR_TASK
    ] = task


async def parar_verificador(
    application: Application,
):
    task = application.bot_data.get(
        VERIFICADOR_TASK
    )

    if task:
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


# =========================================================
# PROCESSAR TEXTO (ROTEADOR)
# =========================================================

async def processar_mensagem_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    if await processar_passo_cadastro(
        update,
        context,
    ):
        return

    if await processar_edicao_campo(
        update,
        context,
    ):
        return

    if await processar_busca(
        update,
        context,
    ):
        return

    if await processar_config_intervalo(
        update,
        context,
    ):
        return


# =========================================================
# BOTÕES (ROTEADOR)
# =========================================================

async def botoes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    if not is_admin(query.from_user.id):
        await query.answer(
            "❌ Acesso negado.",
            show_alert=True,
        )
        return

    await query.answer()

    acao = query.data or ""

    if acao == "menu":
        context.user_data.clear()

        total, ativas = contar_contas()

        await query.edit_message_text(
            "🗂️ *GERENCIADOR DE CONTAS*\n\n"
            f"📦 Total cadastradas: {total}\n"
            f"✅ Ativas: {ativas}\n\n"
            "Escolha uma opção:",
            reply_markup=menu_principal(),
            parse_mode="Markdown",
        )
        return

    if acao == "nova_conta":
        await iniciar_nova_conta(
            query,
            context,
        )
        return

    if acao == "cancelar_cadastro":
        context.user_data.clear()

        await query.edit_message_text(
            "❌ Cadastro cancelado.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ]
                ]
            ),
        )
        return

    if acao.startswith("listar_"):
        try:
            pagina = int(
                acao.replace("listar_", "", 1)
            )
        except ValueError:
            pagina = 1

        await mostrar_lista_contas(
            query,
            pagina,
        )
        return

    if acao.startswith("conta_"):
        try:
            conta_id = int(
                acao.replace("conta_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await mostrar_detalhes_conta(
            query,
            conta_id,
        )
        return

    if acao.startswith("verificar_"):
        try:
            conta_id = int(
                acao.replace("verificar_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        marcar_conta_verificada(conta_id)

        await query.answer(
            "✅ Marcada como verificada!",
            show_alert=True,
        )
        return

    if acao.startswith("toggle_status_"):
        try:
            conta_id = int(
                acao.replace(
                    "toggle_status_", "", 1
                )
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        conta = buscar_conta(conta_id)

        if not conta:
            await query.answer(
                "❌ Conta não encontrada.",
                show_alert=True,
            )
            return

        status_atual = conta[9]

        novo_status = (
            "inativa"
            if status_atual == "ativa"
            else "ativa"
        )

        definir_status_conta(
            conta_id,
            novo_status,
        )

        await mostrar_detalhes_conta(
            query,
            conta_id,
        )
        return

    if acao.startswith("editar_"):
        try:
            conta_id = int(
                acao.replace("editar_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await mostrar_menu_editar(
            query,
            conta_id,
        )
        return

    if acao.startswith("editarcampo_"):
        partes = acao.replace(
            "editarcampo_", "", 1
        ).split("_", 1)

        try:
            conta_id = int(partes[0])
            campo = partes[1]
        except (ValueError, IndexError):
            await query.answer(
                "❌ Dados inválidos.",
                show_alert=True,
            )
            return

        await iniciar_edicao_campo(
            query,
            context,
            conta_id,
            campo,
        )
        return

    if acao.startswith("excluir_"):
        try:
            conta_id = int(
                acao.replace("excluir_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        conta = buscar_conta(conta_id)

        if not conta:
            await query.answer(
                "❌ Conta não encontrada.",
                show_alert=True,
            )
            return

        await query.edit_message_text(
            "⚠️ *EXCLUIR CONTA?*\n\n"
            f"📦 {conta[1]}\n\n"
            "Essa ação não pode ser desfeita.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🗑️ SIM, EXCLUIR",
                            callback_data=(
                                f"confirmarexcluir_{conta_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Cancelar",
                            callback_data=f"conta_{conta_id}",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    if acao.startswith("confirmarexcluir_"):
        try:
            conta_id = int(
                acao.replace(
                    "confirmarexcluir_", "", 1
                )
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        excluir_conta(conta_id)

        await query.edit_message_text(
            "✅ Conta excluída.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ]
                ]
            ),
        )
        return

    if acao == "buscar":
        await iniciar_busca(
            query,
            context,
        )
        return

    if acao == "config_intervalo":
        await iniciar_config_intervalo(
            query,
            context,
        )
        return

    await query.answer(
        "❌ Opção não reconhecida.",
        show_alert=True,
    )


# =========================================================
# ERRO GLOBAL
# =========================================================

async def erro_global(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    print("❌ ERRO GLOBAL:")
    print(repr(context.error))


# =========================================================
# MAIN
# =========================================================

# =========================================================
# COMANDOS DE ATALHO (/nova, /listar, /buscar)
# =========================================================

async def comando_nova(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    context.user_data.clear()
    context.user_data["cadastro_dados"] = {}
    context.user_data["cadastro_passo"] = 0

    _, pergunta = CAMPOS_CADASTRO[0]

    await update.message.reply_text(
        "➕ *NOVA CONTA*\n\n"
        f"{pergunta}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ CANCELAR",
                        callback_data="cancelar_cadastro",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def comando_listar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    contas = listar_contas()

    if not contas:
        await update.message.reply_text(
            "📋 *LISTAR CONTAS*\n\n"
            "Nenhuma conta cadastrada ainda.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Nova conta",
                            callback_data="nova_conta",
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )
        return

    botoes = []

    for conta in contas[:CONTAS_POR_PAGINA]:

        conta_id, servico, email, status = conta

        emoji_status = (
            "✅" if status == "ativa" else "⚫"
        )

        rotulo = f"{emoji_status} {servico}"

        if email:
            rotulo += f" ({email[:20]})"

        botoes.append(
            [
                InlineKeyboardButton(
                    rotulo[:60],
                    callback_data=f"conta_{conta_id}",
                )
            ]
        )

    if len(contas) > CONTAS_POR_PAGINA:
        botoes.append(
            [
                InlineKeyboardButton(
                    "➡️ Ver mais",
                    callback_data="listar_2",
                )
            ]
        )

    await update.message.reply_text(
        "📋 *LISTAR CONTAS*\n\n"
        f"{len(contas)} conta(s) no total:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def comando_buscar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    context.user_data.clear()
    context.user_data["aguardando_busca"] = True

    await update.message.reply_text(
        "🔍 *BUSCAR CONTA*\n\n"
        "Digite o serviço, email ou fornecedor "
        "que você está procurando.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


def main():
    verificar_configuracao()
    criar_tabelas()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(iniciar_verificador)
        .post_shutdown(parar_verificador)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "nova",
            comando_nova,
        )
    )

    application.add_handler(
        CommandHandler(
            "listar",
            comando_listar,
        )
    )

    application.add_handler(
        CommandHandler(
            "buscar",
            comando_buscar,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            botoes
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            processar_mensagem_texto,
        )
    )

    application.add_error_handler(
        erro_global
    )

    print("🗂️ Gerenciador de Contas iniciado!")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
