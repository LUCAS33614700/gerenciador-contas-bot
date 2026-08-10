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
    listar_servicos_distintos,
    listar_tags_distintas,
    buscar_conta,
    buscar_contas_por_termo,
    atualizar_campo_conta,
    definir_status_conta,
    marcar_conta_verificada,
    marcar_varias_verificadas,
    obter_ultima_verificacao_resultado,
    listar_historico_verificacoes,
    excluir_conta,
    listar_contas_para_verificar,
    contar_contas,
    resumo_custos,
    definir_configuracao,
    obter_configuracao,
)


# =========================================================
# CONFIGURAÃ‡Ã•ES GERAIS
# =========================================================

INTERVALO_PADRAO_DIAS = 30
INTERVALO_CHECAGEM_LOOP = 6 * 60 * 60  # a cada 6h
VERIFICADOR_TASK = "verificador_contas_task"
CONTAS_POR_PAGINA = 8

CAMPOS_CADASTRO = [
    ("servico", "ðŸ“º ServiÃ§o (ex: Netflix, Disney+)"),
    ("email", "ðŸ“§ Email/login"),
    ("senha", "ðŸ”‘ Senha"),
    ("data_criacao", "ðŸ—“ï¸ Data de criaÃ§Ã£o (ex: 08/08/2026, ou envie \"pular\")"),
    ("custo_criacao", "ðŸ’° Custo de criaÃ§Ã£o (ex: 15.00, ou envie \"pular\")"),
    ("fornecedor", "ðŸ·ï¸ Fornecedor/origem (ou envie \"pular\")"),
    ("telas_perfis", "ðŸ–¥ï¸ Telas/perfis jÃ¡ usados (ou envie \"pular\")"),
    ("observacoes", "ðŸ“ ObservaÃ§Ãµes gerais (ou envie \"pular\")"),
    ("tags", "ðŸ·ï¸ Tags (ex: vip, revisar â€” separadas por vÃ­rgula, ou envie \"pular\")"),
]

NOMES_CAMPOS = {
    "servico": "ServiÃ§o",
    "email": "Email/login",
    "senha": "Senha",
    "data_criacao": "Data de criaÃ§Ã£o",
    "custo_criacao": "Custo de criaÃ§Ã£o",
    "fornecedor": "Fornecedor",
    "telas_perfis": "Telas/perfis",
    "observacoes": "ObservaÃ§Ãµes",
    "tags": "Tags",
}


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
                "âŒ Este bot Ã© de uso pessoal."
            )
        return

    context.user_data.clear()

    total, ativas = contar_contas()
    total_gasto = resumo_custos()["total_gasto"]

    texto = (
        "ðŸ—‚ï¸ *GERENCIADOR DE CONTAS*\n\n"
        f"ðŸ“¦ Total cadastradas: {total}\n"
        f"âœ… Ativas: {ativas}\n"
        f"ðŸ’° Investido: R$ {total_gasto:.2f}\n\n"
        "Escolha uma opÃ§Ã£o:"
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
                    "âž• NOVA CONTA",
                    callback_data="nova_conta",
                )
            ],
            [
                InlineKeyboardButton(
                    "ðŸ“‹ LISTAR CONTAS",
                    callback_data="listar_1",
                )
            ],
            [
                InlineKeyboardButton(
                    "ðŸ”½ FILTRAR CONTAS",
                    callback_data="filtro_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    "â˜‘ï¸ VERIFICAÃ‡ÃƒO EM LOTE",
                    callback_data="lote_iniciar",
                )
            ],
            [
                InlineKeyboardButton(
                    "ðŸ” BUSCAR",
                    callback_data="buscar",
                )
            ],
            [
                InlineKeyboardButton(
                    "ðŸ’° RESUMO DE CUSTOS",
                    callback_data="resumo_custos",
                )
            ],
            [
                InlineKeyboardButton(
                    "âš™ï¸ INTERVALO DE VERIFICAÃ‡ÃƒO",
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
        "âž• *NOVA CONTA*\n\n"
        f"{pergunta}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ CANCELAR",
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
                "âŒ Digite um nÃºmero vÃ¡lido "
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
                            "âŒ CANCELAR",
                            callback_data="cancelar_cadastro",
                        )
                    ]
                ]
            ),
        )
        return True

    # Ãšltimo passo: salva no banco.
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
        tags=dados.get("tags"),
    )

    context.user_data.clear()

    await update.message.reply_text(
        "âœ… *CONTA CADASTRADA!*\n\n"
        f"ðŸ†” ID: `{conta_id}`\n"
        f"ðŸ“º ServiÃ§o: {dados.get('servico')}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ðŸ“¦ Ver conta",
                        callback_data=f"conta_{conta_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "ðŸ  Menu",
                        callback_data="menu",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# FILTROS DA LISTAGEM
# =========================================================

def obter_contas_filtradas(context):
    return listar_contas(
        servico=context.user_data.get("filtro_servico"),
        status=context.user_data.get("filtro_status"),
        tag=context.user_data.get("filtro_tag"),
    )


def descrever_filtros(context):
    partes = []

    if context.user_data.get("filtro_servico"):
        partes.append(
            f"ðŸ“º {context.user_data['filtro_servico']}"
        )

    if context.user_data.get("filtro_status"):
        rotulo = (
            "Ativas"
            if context.user_data["filtro_status"] == "ativa"
            else "Inativas"
        )
        partes.append(f"ðŸ“Š {rotulo}")

    if context.user_data.get("filtro_tag"):
        partes.append(
            f"ðŸ·ï¸ {context.user_data['filtro_tag']}"
        )

    return " â€¢ ".join(partes)


async def mostrar_filtro_menu(
    query,
    context,
):
    filtros_ativos = descrever_filtros(context)

    botoes = [
        [
            InlineKeyboardButton(
                "ðŸ“º Por serviÃ§o",
                callback_data="filtroservico",
            )
        ],
        [
            InlineKeyboardButton(
                "ðŸ“Š Por status",
                callback_data="filtrostatus",
            )
        ],
    ]

    if listar_tags_distintas():
        botoes.append(
            [
                InlineKeyboardButton(
                    "ðŸ·ï¸ Por tag",
                    callback_data="filtrotag",
                )
            ]
        )

    if filtros_ativos:
        botoes.append(
            [
                InlineKeyboardButton(
                    "ðŸ§¹ Limpar filtros",
                    callback_data="filtrolimpar",
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "ðŸ“‹ Ver lista",
                callback_data="listar_1",
            )
        ]
    )
    botoes.append(
        [
            InlineKeyboardButton(
                "ðŸ  Menu",
                callback_data="menu",
            )
        ]
    )

    texto = "ðŸ”½ *FILTRAR CONTAS*\n\n"

    if filtros_ativos:
        texto += f"Filtro(s) ativo(s): {filtros_ativos}\n\n"

    texto += "Escolha como filtrar:"

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_filtro_servico(
    query,
    context,
):
    servicos = listar_servicos_distintos()

    if not servicos:
        await query.answer(
            "âŒ Nenhum serviÃ§o cadastrado ainda.",
            show_alert=True,
        )
        return

    botoes = [
        [
            InlineKeyboardButton(
                servico,
                callback_data=f"setfiltroservico_{servico}",
            )
        ]
        for servico in servicos
    ]

    botoes.append(
        [
            InlineKeyboardButton(
                "â¬…ï¸ Voltar",
                callback_data="filtro_menu",
            )
        ]
    )

    await query.edit_message_text(
        "ðŸ“º *FILTRAR POR SERVIÃ‡O*\n\n"
        "Escolha o serviÃ§o:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_filtro_status(
    query,
    context,
):
    botoes = [
        [
            InlineKeyboardButton(
                "âœ… SÃ³ ativas",
                callback_data="setfiltrostatus_ativa",
            )
        ],
        [
            InlineKeyboardButton(
                "âš« SÃ³ inativas",
                callback_data="setfiltrostatus_inativa",
            )
        ],
        [
            InlineKeyboardButton(
                "â¬…ï¸ Voltar",
                callback_data="filtro_menu",
            )
        ],
    ]

    await query.edit_message_text(
        "ðŸ“Š *FILTRAR POR STATUS*\n\n"
        "Escolha o status:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_filtro_tag(
    query,
    context,
):
    tags = listar_tags_distintas()

    if not tags:
        await query.answer(
            "âŒ Nenhuma tag cadastrada ainda.",
            show_alert=True,
        )
        return

    botoes = [
        [
            InlineKeyboardButton(
                f"ðŸ·ï¸ {tag}",
                callback_data=f"setfiltrotag_{tag}",
            )
        ]
        for tag in tags
    ]

    botoes.append(
        [
            InlineKeyboardButton(
                "â¬…ï¸ Voltar",
                callback_data="filtro_menu",
            )
        ]
    )

    await query.edit_message_text(
        "ðŸ·ï¸ *FILTRAR POR TAG*\n\n"
        "Escolha a tag:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# LISTAR CONTAS (COM PAGINAÃ‡ÃƒO E FILTROS)
# =========================================================

async def mostrar_lista_contas(
    query,
    context,
    pagina=1,
):
    contas = obter_contas_filtradas(context)
    filtros_ativos = descrever_filtros(context)

    if not contas:
        texto = "ðŸ“‹ *LISTAR CONTAS*\n\n"

        if filtros_ativos:
            texto += f"Filtro(s): {filtros_ativos}\n\n"

        texto += "Nenhuma conta encontrada."

        botoes = []

        if filtros_ativos:
            botoes.append(
                [
                    InlineKeyboardButton(
                        "ðŸ§¹ Limpar filtros",
                        callback_data="filtrolimpar",
                    )
                ]
            )

        botoes.append(
            [
                InlineKeyboardButton(
                    "âž• Nova conta",
                    callback_data="nova_conta",
                )
            ]
        )
        botoes.append(
            [
                InlineKeyboardButton(
                    "ðŸ  Menu",
                    callback_data="menu",
                )
            ]
        )

        await query.edit_message_text(
            texto,
            reply_markup=InlineKeyboardMarkup(
                botoes
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
            "âœ…" if status == "ativa" else "âš«"
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
                "â¬…ï¸",
                callback_data=f"listar_{pagina - 1}",
            )
        )

    if pagina < total_paginas:
        navegacao.append(
            InlineKeyboardButton(
                "âž¡ï¸",
                callback_data=f"listar_{pagina + 1}",
            )
        )

    if navegacao:
        botoes.append(navegacao)

    botoes.append(
        [
            InlineKeyboardButton(
                "ðŸ”½ Filtrar",
                callback_data="filtro_menu",
            )
        ]
    )
    botoes.append(
        [
            InlineKeyboardButton(
                "ðŸ  Menu",
                callback_data="menu",
            )
        ]
    )

    texto = "ðŸ“‹ *LISTAR CONTAS*\n\n"

    if filtros_ativos:
        texto += f"Filtro(s): {filtros_ativos}\n\n"

    texto += (
        f"PÃ¡gina {pagina}/{total_paginas} â€” "
        f"{len(contas)} conta(s) no total:"
    )

    await query.edit_message_text(
        texto,
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
            "âŒ Conta nÃ£o encontrada.",
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
        tags,
    ) = conta

    emoji_status = (
        "âœ… Ativa" if status == "ativa" else "âš« Inativa"
    )

    ultimo_resultado = obter_ultima_verificacao_resultado(
        conta_id
    )

    linha_resultado = ""
    if ultimo_resultado:
        resultado_valor, _ = ultimo_resultado
        emoji_resultado = (
            "âœ… OK" if resultado_valor == "ok" else "âš ï¸ Problema"
        )
        linha_resultado = f" ({emoji_resultado})"

    senha_oculta = "â€¢" * 10 if senha else "â€”"

    texto = (
        f"ðŸ“¦ *{servico}*\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"ðŸ“§ Email: {email or 'â€”'}\n"
        f"ðŸ”‘ Senha: `{senha_oculta}`\n"
        f"ðŸ—“ï¸ Criada em: {data_criacao or 'â€”'}\n"
        f"ðŸ’° Custo: "
        f"{f'R$ {custo_criacao:.2f}' if custo_criacao else 'â€”'}\n"
        f"ðŸ·ï¸ Fornecedor: {fornecedor or 'â€”'}\n"
        f"ðŸ–¥ï¸ Telas/perfis: {telas_perfis or 'â€”'}\n"
        f"ðŸ“ Obs: {observacoes or 'â€”'}\n"
        f"ðŸ·ï¸ Tags: {tags or 'â€”'}\n"
        f"ðŸ“Š Status: {emoji_status}\n"
        f"ðŸ”Ž Ãšltima verificaÃ§Ã£o: "
        f"{str(ultima_verificacao)[:16]}{linha_resultado}\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
    )

    botoes = [
        [
            InlineKeyboardButton(
                "ðŸ‘ï¸ MOSTRAR SENHA",
                callback_data=f"senha_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "âœ… MARCAR COMO VERIFICADA",
                callback_data=f"verificarmenu_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "ðŸ“œ HISTÃ“RICO DE VERIFICAÃ‡Ã•ES",
                callback_data=f"historico_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "âœï¸ EDITAR",
                callback_data=f"editar_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                (
                    "âš« MARCAR INATIVA"
                    if status == "ativa"
                    else "âœ… MARCAR ATIVA"
                ),
                callback_data=f"toggle_status_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "ðŸ—‘ï¸ EXCLUIR",
                callback_data=f"excluir_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "ðŸ  Menu",
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
# HISTÃ“RICO DE VERIFICAÃ‡Ã•ES
# =========================================================

async def mostrar_historico_conta(
    query,
    conta_id,
):
    conta = buscar_conta(conta_id)

    if not conta:
        await query.answer(
            "âŒ Conta nÃ£o encontrada.",
            show_alert=True,
        )
        return

    historico = listar_historico_verificacoes(
        conta_id,
        10,
    )

    texto = f"ðŸ“œ *HISTÃ“RICO â€” {conta[1]}*\n\n"

    if not historico:
        texto += "Nenhuma verificaÃ§Ã£o registrada ainda."
    else:
        for resultado_valor, data_valor in historico:
            emoji_resultado = (
                "âœ… OK"
                if resultado_valor == "ok"
                else "âš ï¸ Problema"
            )
            texto += (
                f"{emoji_resultado} â€” "
                f"{str(data_valor)[:16]}\n"
            )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "â¬…ï¸ Voltar",
                        callback_data=f"conta_{conta_id}",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


# =========================================================
# EDITAR CAMPO
# =========================================================

async def mostrar_menu_editar(
    query,
    conta_id,
):
    botoes = []

    for campo, nome in NOMES_CAMPOS.items():
        botoes.append(
            [
                InlineKeyboardButton(
                    f"âœï¸ {nome}",
                    callback_data=(
                        f"editarcampo_{conta_id}_{campo}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "â¬…ï¸ Voltar",
                callback_data=f"conta_{conta_id}",
            )
        ]
    )

    await query.edit_message_text(
        "âœï¸ *EDITAR CONTA*\n\n"
        "Qual campo vocÃª quer alterar?",
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
        f"âœï¸ *EDITAR {nome_campo.upper()}*\n\n"
        "Digite o novo valor:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ Cancelar",
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
                "âŒ Digite um nÃºmero vÃ¡lido "
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
        "âœ… Campo atualizado!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ðŸ“¦ Ver conta",
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
        "ðŸ” *BUSCAR CONTA*\n\n"
        "Digite o serviÃ§o, email, fornecedor ou tag "
        "que vocÃª estÃ¡ procurando.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ Cancelar",
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
            f"âŒ Nenhum resultado para \"{termo}\".",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ðŸ  Menu",
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
            "âœ…" if status == "ativa" else "âš«"
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
                "ðŸ  Menu",
                callback_data="menu",
            )
        ]
    )

    await update.message.reply_text(
        f"ðŸ” *RESULTADOS PARA* \"{termo}\":",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# RESUMO DE CUSTOS
# =========================================================

async def mostrar_resumo_custos(
    query,
    context,
):
    resumo = resumo_custos()

    texto = (
        "ðŸ’° *RESUMO DE CUSTOS*\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"ðŸ“¦ Total de contas: {resumo['total_contas']}\n"
        f"ðŸ’µ Com custo informado: "
        f"{resumo['contas_com_custo']}\n\n"
        f"ðŸ’° Total investido: "
        f"R$ {resumo['total_gasto']:.2f}\n"
        f"âœ… Em contas ativas: "
        f"R$ {resumo['gasto_ativas']:.2f}\n"
        f"âš« Em contas inativas: "
        f"R$ {resumo['gasto_inativas']:.2f}\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
    )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ðŸ  Menu",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


# =========================================================
# VERIFICAÃ‡ÃƒO EM LOTE
# =========================================================

async def mostrar_lote_verificacao(
    query,
    context,
    pagina=1,
):
    contas = listar_contas(apenas_ativas=True)

    selecionados = context.user_data.setdefault(
        "lote_selecionados",
        set(),
    )

    if not contas:
        await query.edit_message_text(
            "â˜‘ï¸ *VERIFICAÃ‡ÃƒO EM LOTE*\n\n"
            "Nenhuma conta ativa cadastrada.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ðŸ  Menu",
                            callback_data="menu",
                        )
                    ]
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

        marcado = "â˜‘ï¸" if conta_id in selecionados else "â¬œ"

        rotulo = f"{marcado} {servico}"

        if email:
            rotulo += f" ({email[:15]})"

        botoes.append(
            [
                InlineKeyboardButton(
                    rotulo[:60],
                    callback_data=(
                        f"loteToggle_{conta_id}_{pagina}"
                    ),
                )
            ]
        )

    navegacao = []

    if pagina > 1:
        navegacao.append(
            InlineKeyboardButton(
                "â¬…ï¸",
                callback_data=f"lotepag_{pagina - 1}",
            )
        )

    if pagina < total_paginas:
        navegacao.append(
            InlineKeyboardButton(
                "âž¡ï¸",
                callback_data=f"lotepag_{pagina + 1}",
            )
        )

    if navegacao:
        botoes.append(navegacao)

    if selecionados:
        botoes.append(
            [
                InlineKeyboardButton(
                    f"âœ… Marcar {len(selecionados)} como OK",
                    callback_data="loteconfirmar_ok",
                )
            ]
        )
        botoes.append(
            [
                InlineKeyboardButton(
                    f"âš ï¸ Marcar {len(selecionados)} c/ problema",
                    callback_data="loteconfirmar_problema",
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "ðŸ  Menu",
                callback_data="menu",
            )
        ]
    )

    texto = (
        "â˜‘ï¸ *VERIFICAÃ‡ÃƒO EM LOTE*\n\n"
        f"PÃ¡gina {pagina}/{total_paginas} â€” toque pra "
        "selecionar as contas que vocÃª jÃ¡ checou.\n"
        f"Selecionadas: {len(selecionados)}"
    )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# CONFIGURAR INTERVALO DE VERIFICAÃ‡ÃƒO
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
        "âš™ï¸ *INTERVALO DE VERIFICAÃ‡ÃƒO*\n\n"
        f"ðŸ“‹ Valor atual: {atual} dias\n\n"
        "Digite de quantos em quantos dias "
        "vocÃª quer ser lembrado de verificar "
        "cada conta.\n\n"
        "Exemplo:\n"
        "`30`\n"
        "`15`",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ Cancelar",
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
            "âŒ Digite um nÃºmero inteiro maior "
            "que zero."
        )
        return True

    definir_configuracao(
        "intervalo_dias",
        texto,
    )

    context.user_data.clear()

    await update.message.reply_text(
        "âœ… *INTERVALO ATUALIZADO!*\n\n"
        f"âš™ï¸ Novo valor: {texto} dias",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ðŸ  Menu",
                        callback_data="menu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )

    return True


# =========================================================
# VERIFICADOR AUTOMÃTICO (LOOP EM BACKGROUND)
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
            "ðŸ”” *CONTAS PRA VERIFICAR*\n\n"
            f"As contas abaixo nÃ£o sÃ£o checadas "
            f"hÃ¡ {intervalo}+ dias:\n\n"
            "Toque em âœ… OK ou âš ï¸ Problema pra "
            "cada uma, ou use â˜‘ï¸ VERIFICAÃ‡ÃƒO EM "
            "LOTE no menu pra marcar vÃ¡rias juntas."
        )

        botoes = []

        for conta in pendentes[:15]:

            conta_id, servico, email, _ = conta

            botoes.append(
                [
                    InlineKeyboardButton(
                        f"âœ… OK: {servico[:18]}",
                        callback_data=f"verificarok_{conta_id}",
                    ),
                    InlineKeyboardButton(
                        f"âš ï¸ Problema",
                        callback_data=(
                            f"verificarproblema_{conta_id}"
                        ),
                    ),
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
        "ðŸ”” Verificador de contas iniciado."
    )

    while True:
        try:
            await checar_contas_pendentes(
                application.bot
            )

        except asyncio.CancelledError:
            print(
                "ðŸ”” Verificador de contas encerrado."
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
# BOTÃ•ES (ROTEADOR)
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
            "âŒ Acesso negado.",
            show_alert=True,
        )
        return

    await query.answer()

    acao = query.data or ""

    if acao == "menu":
        context.user_data.clear()

        total, ativas = contar_contas()
        total_gasto = resumo_custos()["total_gasto"]

        await query.edit_message_text(
            "ðŸ—‚ï¸ *GERENCIADOR DE CONTAS*\n\n"
            f"ðŸ“¦ Total cadastradas: {total}\n"
            f"âœ… Ativas: {ativas}\n"
            f"ðŸ’° Investido: R$ {total_gasto:.2f}\n\n"
            "Escolha uma opÃ§Ã£o:",
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
            "âŒ Cadastro cancelado.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ðŸ  Menu",
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
            context,
            pagina,
        )
        return

    if acao == "filtro_menu":
        await mostrar_filtro_menu(
            query,
            context,
        )
        return

    if acao == "filtroservico":
        await mostrar_filtro_servico(
            query,
            context,
        )
        return

    if acao == "filtrostatus":
        await mostrar_filtro_status(
            query,
            context,
        )
        return

    if acao == "filtrotag":
        await mostrar_filtro_tag(
            query,
            context,
        )
        return

    if acao == "filtrolimpar":
        context.user_data.pop("filtro_servico", None)
        context.user_data.pop("filtro_status", None)
        context.user_data.pop("filtro_tag", None)

        await mostrar_lista_contas(
            query,
            context,
            1,
        )
        return

    if acao.startswith("setfiltroservico_"):
        context.user_data["filtro_servico"] = (
            acao.replace("setfiltroservico_", "", 1)
        )

        await mostrar_lista_contas(
            query,
            context,
            1,
        )
        return

    if acao.startswith("setfiltrostatus_"):
        context.user_data["filtro_status"] = (
            acao.replace("setfiltrostatus_", "", 1)
        )

        await mostrar_lista_contas(
            query,
            context,
            1,
        )
        return

    if acao.startswith("setfiltrotag_"):
        context.user_data["filtro_tag"] = (
            acao.replace("setfiltrotag_", "", 1)
        )

        await mostrar_lista_contas(
            query,
            context,
            1,
        )
        return

    if acao.startswith("conta_"):
        try:
            conta_id = int(
                acao.replace("conta_", "", 1)
            )
        except ValueError:
            await query.answer(
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        await mostrar_detalhes_conta(
            query,
            conta_id,
        )
        return

    if acao.startswith("senha_"):
        try:
            conta_id = int(
                acao.replace("senha_", "", 1)
            )
        except ValueError:
            await query.answer(
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        conta = buscar_conta(conta_id)

        if not conta:
            await query.answer(
                "âŒ Conta nÃ£o encontrada.",
                show_alert=True,
            )
            return

        senha = conta[3]

        await query.answer(
            f"ðŸ”‘ Senha: {senha or 'â€” (nÃ£o cadastrada)'}",
            show_alert=True,
        )
        return

    if acao.startswith("verificarmenu_"):
        try:
            conta_id = int(
                acao.replace("verificarmenu_", "", 1)
            )
        except ValueError:
            await query.answer(
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        await query.edit_message_text(
            "âœ… *MARCAR COMO VERIFICADA*\n\n"
            "Como estÃ¡ a conta?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "âœ… OK, tudo certo",
                            callback_data=(
                                f"verificarok_{conta_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "âš ï¸ Com problema",
                            callback_data=(
                                f"verificarproblema_{conta_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "âŒ Cancelar",
                            callback_data=f"conta_{conta_id}",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    if acao.startswith("verificarok_") or acao.startswith(
        "verificarproblema_"
    ):
        resultado = (
            "ok" if acao.startswith("verificarok_") else "problema"
        )
        prefixo = (
            "verificarok_"
            if resultado == "ok"
            else "verificarproblema_"
        )

        try:
            conta_id = int(
                acao.replace(prefixo, "", 1)
            )
        except ValueError:
            await query.answer(
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        marcar_conta_verificada(conta_id, resultado)

        emoji_resultado = (
            "âœ… OK" if resultado == "ok" else "âš ï¸ Com problema"
        )

        await query.answer(
            f"Marcada como verificada! {emoji_resultado}",
            show_alert=True,
        )

        await mostrar_detalhes_conta(
            query,
            conta_id,
        )
        return

    if acao.startswith("historico_"):
        try:
            conta_id = int(
                acao.replace("historico_", "", 1)
            )
        except ValueError:
            await query.answer(
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        await mostrar_historico_conta(
            query,
            conta_id,
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
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        conta = buscar_conta(conta_id)

        if not conta:
            await query.answer(
                "âŒ Conta nÃ£o encontrada.",
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
                "âŒ Conta invÃ¡lida.",
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
                "âŒ Dados invÃ¡lidos.",
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
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        conta = buscar_conta(conta_id)

        if not conta:
            await query.answer(
                "âŒ Conta nÃ£o encontrada.",
                show_alert=True,
            )
            return

        await query.edit_message_text(
            "âš ï¸ *EXCLUIR CONTA?*\n\n"
            f"ðŸ“¦ {conta[1]}\n\n"
            "Essa aÃ§Ã£o nÃ£o pode ser desfeita.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ðŸ—‘ï¸ SIM, EXCLUIR",
                            callback_data=(
                                f"confirmarexcluir_{conta_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "âŒ Cancelar",
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
                "âŒ Conta invÃ¡lida.",
                show_alert=True,
            )
            return

        excluir_conta(conta_id)

        await query.edit_message_text(
            "âœ… Conta excluÃ­da.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ðŸ  Menu",
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

    if acao == "resumo_custos":
        await mostrar_resumo_custos(
            query,
            context,
        )
        return

    if acao == "lote_iniciar":
        context.user_data["lote_selecionados"] = set()

        await mostrar_lote_verificacao(
            query,
            context,
            1,
        )
        return

    if acao.startswith("lotepag_"):
        try:
            pagina = int(
                acao.replace("lotepag_", "", 1)
            )
        except ValueError:
            pagina = 1

        await mostrar_lote_verificacao(
            query,
            context,
            pagina,
        )
        return

    if acao.startswith("loteToggle_"):
        partes = acao.replace(
            "loteToggle_", "", 1
        ).split("_")

        try:
            conta_id = int(partes[0])
            pagina_atual = (
                int(partes[1]) if len(partes) > 1 else 1
            )
        except (ValueError, IndexError):
            await query.answer(
                "âŒ Dados invÃ¡lidos.",
                show_alert=True,
            )
            return

        selecionados = context.user_data.setdefault(
            "lote_selecionados",
            set(),
        )

        if conta_id in selecionados:
            selecionados.discard(conta_id)
        else:
            selecionados.add(conta_id)

        await mostrar_lote_verificacao(
            query,
            context,
            pagina_atual,
        )
        return

    if acao.startswith("loteconfirmar_"):
        resultado = acao.replace(
            "loteconfirmar_", "", 1
        )

        selecionados = context.user_data.get(
            "lote_selecionados",
            set(),
        )

        quantidade = marcar_varias_verificadas(
            list(selecionados),
            resultado,
        )

        context.user_data["lote_selecionados"] = set()

        emoji_resultado = (
            "âœ… OK" if resultado == "ok" else "âš ï¸ Com problema"
        )

        await query.edit_message_text(
            f"âœ… *{quantidade} CONTA(S) VERIFICADA(S)!*\n\n"
            f"Resultado: {emoji_resultado}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "â˜‘ï¸ Verificar mais",
                            callback_data="lote_iniciar",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "ðŸ  Menu",
                            callback_data="menu",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    if acao == "config_intervalo":
        await iniciar_config_intervalo(
            query,
            context,
        )
        return

    await query.answer(
        "âŒ OpÃ§Ã£o nÃ£o reconhecida.",
        show_alert=True,
    )


# =========================================================
# ERRO GLOBAL
# =========================================================

async def erro_global(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    print("âŒ ERRO GLOBAL:")
    print(repr(context.error))


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
        "âž• *NOVA CONTA*\n\n"
        f"{pergunta}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ CANCELAR",
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
            "ðŸ“‹ *LISTAR CONTAS*\n\n"
            "Nenhuma conta cadastrada ainda.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "âž• Nova conta",
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
            "âœ…" if status == "ativa" else "âš«"
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
                    "âž¡ï¸ Ver mais",
                    callback_data="listar_2",
                )
            ]
        )

    await update.message.reply_text(
        "ðŸ“‹ *LISTAR CONTAS*\n\n"
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
        "ðŸ” *BUSCAR CONTA*\n\n"
        "Digite o serviÃ§o, email, fornecedor ou tag "
        "que vocÃª estÃ¡ procurando.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "âŒ Cancelar",
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

    print("ðŸ—‚ï¸ Gerenciador de Contas iniciado!")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
