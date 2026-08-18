import asyncio
import csv
import io
from datetime import datetime, date

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
    listar_contas_filtrado,
    listar_servicos_distintos,
    buscar_conta,
    buscar_contas_por_termo,
    atualizar_campo_conta,
    definir_status_conta,
    marcar_conta_verificada,
    listar_historico_verificacoes,
    excluir_conta,
    listar_contas_para_verificar,
    contar_contas,
    definir_configuracao,
    obter_configuracao,
    obter_resumo_custos,
    obter_custo_por_servico,
    verificar_todas_pendentes,
    contar_contas_por_servico,
    listar_contas_com_vencimento,
    marcar_vencimento_notificado,
    obter_todas_contas_para_exportar,
)


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

INTERVALO_PADRAO_DIAS = 30
INTERVALO_CHECAGEM_LOOP = 6 * 60 * 60  # a cada 6h
VERIFICADOR_TASK = "verificador_contas_task"
DIAS_AVISO_VENCIMENTO = 3

CAMPOS_CADASTRO = [
    ("servico", "📺 Serviço (ex: Netflix, Disney+)"),
    ("email", "📧 Email/login"),
    ("senha", "🔑 Senha"),
    ("data_criacao", "🗓️ Data de criação (ex: 08/08/2026, ou envie \"pular\")"),
    ("data_vencimento", "⏰ Data de vencimento/renovação (ex: 08/09/2026 — obrigatório)"),
    ("custo_criacao", "💰 Custo de criação (ex: 15.00, ou envie \"pular\")"),
    ("fornecedor", "🏷️ Fornecedor/origem (ou envie \"pular\")"),
    ("telas_perfis", "🖥️ Telas/perfis já usados (ou envie \"pular\")"),
    ("tags", "🏷️ Tags, separadas por vírgula (ex: vip, revisar, ou envie \"pular\")"),
    ("observacoes", "📝 Observações gerais (ou envie \"pular\")"),
]

CAMPOS_DATA = ("data_criacao", "data_vencimento")


def parse_data_br(texto):
    """Converte DD/MM/AAAA em date, ou retorna None se inválido."""
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        return None


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
                    "📂 CATEGORIAS",
                    callback_data="categorias",
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
                    "✅ VERIFICAÇÃO EM LOTE",
                    callback_data="lote_iniciar",
                )
            ],
            [
                InlineKeyboardButton(
                    "💰 RESUMO DE CUSTOS",
                    callback_data="resumo_custos",
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ INTERVALO DE VERIFICAÇÃO",
                    callback_data="config_intervalo",
                )
            ],
            [
                InlineKeyboardButton(
                    "📤 EXPORTAR CSV",
                    callback_data="exportar_csv",
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

    if campo == "data_vencimento":
        if texto.lower() == "pular":
            await update.message.reply_text(
                "❌ A data de vencimento é "
                "obrigatória. Digite no formato "
                "DD/MM/AAAA (ex: 08/09/2026)."
            )
            return True
        if not parse_data_br(texto):
            await update.message.reply_text(
                "❌ Data inválida. Use o formato "
                "DD/MM/AAAA (ex: 08/09/2026)."
            )
            return True
        valor = texto
    elif texto.lower() == "pular":
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
    elif campo in CAMPOS_DATA and not parse_data_br(texto):
        await update.message.reply_text(
            "❌ Data inválida. Use o formato "
            "DD/MM/AAAA (ex: 08/09/2026) ou "
            "\"pular\"."
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
        tags=dados.get("tags"),
        data_vencimento=dados.get("data_vencimento"),
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
    context,
    pagina=1,
):
    filtro_servico = context.user_data.get(
        "filtro_servico"
    )
    filtro_status = context.user_data.get(
        "filtro_status"
    )

    if filtro_servico or filtro_status:
        contas = listar_contas_filtrado(
            servico=filtro_servico,
            status=filtro_status,
        )
    else:
        contas = listar_contas()

    linha_filtro = []

    if filtro_servico or filtro_status:

        descricao_filtro = []

        if filtro_servico:
            descricao_filtro.append(filtro_servico)

        if filtro_status:
            descricao_filtro.append(
                "Ativas"
                if filtro_status == "ativa"
                else "Inativas"
            )

        linha_filtro.append(
            InlineKeyboardButton(
                f"🔽 Filtro: {' + '.join(descricao_filtro)}",
                callback_data="filtrar_menu",
            )
        )
        linha_filtro.append(
            InlineKeyboardButton(
                "🔄 Limpar",
                callback_data="limpar_filtros",
            )
        )
    else:
        linha_filtro.append(
            InlineKeyboardButton(
                "🔽 Filtrar",
                callback_data="filtrar_menu",
            )
        )

    if not contas:
        botoes_vazio = [linha_filtro]
        botoes_vazio.append(
            [
                InlineKeyboardButton(
                    "➕ Nova conta",
                    callback_data="nova_conta",
                )
            ]
        )
        botoes_vazio.append(
            [
                InlineKeyboardButton(
                    "🏠 Menu",
                    callback_data="menu",
                )
            ]
        )

        await query.edit_message_text(
            "📋 *LISTAR CONTAS*\n\n"
            "Nenhuma conta encontrada com esse "
            "filtro.",
            reply_markup=InlineKeyboardMarkup(
                botoes_vazio
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

    botoes = [linha_filtro]

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
        f"{len(contas)} conta(s):",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# FILTROS
# =========================================================

async def mostrar_menu_filtro(
    query,
    context,
):
    await query.edit_message_text(
        "🔽 *FILTRAR CONTAS*\n\n"
        "Escolha como filtrar:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📺 Por Serviço",
                        callback_data="filtrar_servico",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📊 Por Status",
                        callback_data="filtrar_status",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Limpar Filtros",
                        callback_data="limpar_filtros",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Voltar",
                        callback_data="listar_1",
                    )
                ],
            ]
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
            "❌ Nenhum serviço cadastrado ainda.",
            show_alert=True,
        )
        return

    context.user_data["servicos_disponiveis"] = (
        servicos
    )

    botoes = []

    for indice, servico in enumerate(servicos):
        botoes.append(
            [
                InlineKeyboardButton(
                    servico[:60],
                    callback_data=(
                        f"setfiltroservico_{indice}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "⬅️ Voltar",
                callback_data="filtrar_menu",
            )
        ]
    )

    await query.edit_message_text(
        "📺 *FILTRAR POR SERVIÇO*\n\n"
        "Escolha o serviço:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_filtro_status(
    query,
    context,
):
    await query.edit_message_text(
        "📊 *FILTRAR POR STATUS*\n\n"
        "Escolha o status:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Ativas",
                        callback_data=(
                            "setfiltrostatus_ativa"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⚫ Inativas",
                        callback_data=(
                            "setfiltrostatus_inativa"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Voltar",
                        callback_data="filtrar_menu",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


# =========================================================
# CATEGORIAS (SERVIÇO)
# =========================================================

async def mostrar_categorias(
    query,
    context,
):
    categorias = contar_contas_por_servico()

    if not categorias:
        await query.edit_message_text(
            "📂 *CATEGORIAS*\n\n"
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

    context.user_data["servicos_disponiveis"] = [
        linha[0] for linha in categorias
    ]

    botoes = []

    for indice, (servico, total, ativas) in enumerate(
        categorias
    ):
        rotulo = f"📺 {servico} ({ativas}/{total})"

        botoes.append(
            [
                InlineKeyboardButton(
                    rotulo[:60],
                    callback_data=(
                        f"setfiltroservico_{indice}"
                    ),
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

    await query.edit_message_text(
        "📂 *CATEGORIAS*\n\n"
        "Toque numa categoria pra ver só as "
        "contas dela (ativas/total):",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# RESUMO DE CUSTOS
# =========================================================

async def mostrar_resumo_custos(
    query,
    context,
):
    total, total_ativas, quantidade = (
        obter_resumo_custos()
    )

    por_servico = obter_custo_por_servico()

    texto = (
        "💰 *RESUMO DE CUSTOS*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Total investido:* R$ {total:.2f}\n"
        f"✅ *Em contas ativas:* "
        f"R$ {total_ativas:.2f}\n"
        f"📦 *Contas com custo informado:* "
        f"{quantidade}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "*Por serviço:*\n\n"
    )

    for servico, soma, qtd in por_servico:
        texto += (
            f"📺 {servico}: R$ {soma:.2f} "
            f"({qtd} conta(s))\n"
        )

    await query.edit_message_text(
        texto,
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


# =========================================================
# EXPORTAR CSV
# =========================================================

CABECALHO_EXPORT_CSV = [
    "id",
    "servico",
    "email",
    "senha",
    "data_criacao",
    "data_vencimento",
    "custo_criacao",
    "fornecedor",
    "telas_perfis",
    "tags",
    "observacoes",
    "status",
    "ultima_verificacao",
    "criado_em",
]


async def exportar_contas_csv(
    query,
    context,
):
    contas = obter_todas_contas_para_exportar()

    if not contas:
        await query.answer(
            "❌ Nenhuma conta cadastrada ainda.",
            show_alert=True,
        )
        return

    buffer_texto = io.StringIO()
    escritor = csv.writer(buffer_texto)

    escritor.writerow(CABECALHO_EXPORT_CSV)

    for linha in contas:
        escritor.writerow(linha)

    buffer_bytes = io.BytesIO(
        buffer_texto.getvalue().encode("utf-8-sig")
    )
    buffer_bytes.name = (
        f"contas_{date.today().isoformat()}.csv"
    )

    await query.message.reply_document(
        document=buffer_bytes,
        filename=buffer_bytes.name,
        caption=(
            "📤 *EXPORTAÇÃO CONCLUÍDA*\n\n"
            f"📦 {len(contas)} conta(s) exportada(s).\n"
            "⚠️ Este arquivo contém as senhas em "
            "texto puro — guarde com cuidado."
        ),
        parse_mode="Markdown",
    )


# =========================================================
# VERIFICAÇÃO EM LOTE
# =========================================================

async def mostrar_confirmacao_lote(
    query,
    context,
):
    intervalo = int(
        obter_configuracao("intervalo_dias")
        or INTERVALO_PADRAO_DIAS
    )

    pendentes = listar_contas_para_verificar(
        intervalo
    )

    if not pendentes:
        await query.edit_message_text(
            "✅ *VERIFICAÇÃO EM LOTE*\n\n"
            "Nenhuma conta pendente de "
            "verificação no momento. 🎉",
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
        return

    texto = (
        "✅ *VERIFICAÇÃO EM LOTE*\n\n"
        f"{len(pendentes)} conta(s) pendente(s):\n\n"
    )

    for conta in pendentes[:15]:
        _, servico, email, _ = conta
        texto += f"📦 {servico}"
        if email:
            texto += f" ({email[:20]})"
        texto += "\n"

    if len(pendentes) > 15:
        texto += (
            f"\n_...e mais {len(pendentes) - 15}._\n"
        )

    texto += (
        "\nMarcar todas como *✅ OK, "
        "funcionando* de uma vez?"
    )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ SIM, MARCAR TODAS",
                        callback_data="lote_confirmar",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="menu",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


async def executar_lote(
    query,
    context,
):
    intervalo = int(
        obter_configuracao("intervalo_dias")
        or INTERVALO_PADRAO_DIAS
    )

    quantidade = verificar_todas_pendentes(
        intervalo,
        "ok",
    )

    await query.edit_message_text(
        "✅ *VERIFICAÇÃO EM LOTE CONCLUÍDA!*\n\n"
        f"{quantidade} conta(s) marcada(s) "
        "como OK.",
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


# =========================================================
# DETALHES DA CONTA
# =========================================================

async def mostrar_detalhes_conta(
    query,
    conta_id,
    mostrar_senha=False,
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
        tags,
        ultimo_resultado,
        contagem_problemas,
        data_vencimento,
        _vencimento_notificado_em,
    ) = conta

    texto_vencimento = data_vencimento or "—"
    data_venc_obj = (
        parse_data_br(data_vencimento)
        if data_vencimento
        else None
    )

    if data_venc_obj:
        dias_restantes = (
            data_venc_obj - date.today()
        ).days

        if dias_restantes < 0:
            texto_vencimento += (
                f" (⚠️ vencida há "
                f"{abs(dias_restantes)} dia(s))"
            )
        elif dias_restantes <= DIAS_AVISO_VENCIMENTO:
            texto_vencimento += (
                f" (⏰ faltam {dias_restantes} "
                f"dia(s))"
            )

    emoji_status = (
        "✅ Ativa" if status == "ativa" else "⚫ Inativa"
    )

    if mostrar_senha:
        texto_senha = f"`{senha or '—'}`"
    else:
        texto_senha = "🔒 Oculta"

    if ultimo_resultado == "problema":
        texto_resultado = "⚠️ Com problema"
    elif ultimo_resultado == "ok":
        texto_resultado = "✅ OK"
    else:
        texto_resultado = "—"

    texto = (
        f"📦 *{servico}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📧 Email: {email or '—'}\n"
        f"🔑 Senha: {texto_senha}\n"
        f"🗓️ Criada em: {data_criacao or '—'}\n"
        f"⏰ Vencimento: {texto_vencimento}\n"
        f"💰 Custo: "
        f"{f'R$ {custo_criacao:.2f}' if custo_criacao else '—'}\n"
        f"🏷️ Fornecedor: {fornecedor or '—'}\n"
        f"🖥️ Telas/perfis: {telas_perfis or '—'}\n"
        f"🏷️ Tags: {tags or '—'}\n"
        f"📝 Obs: {observacoes or '—'}\n"
        f"📊 Status: {emoji_status}\n"
        f"🔎 Última verificação: "
        f"{str(ultima_verificacao)[:16]} "
        f"({texto_resultado})\n"
        f"⚠️ Problemas registrados: "
        f"{contagem_problemas or 0}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    botoes = [
        [
            InlineKeyboardButton(
                (
                    "🙈 OCULTAR SENHA"
                    if mostrar_senha
                    else "👁️ MOSTRAR SENHA"
                ),
                callback_data=(
                    f"ocultarsenha_{conta_id}"
                    if mostrar_senha
                    else f"mostrarsenha_{conta_id}"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                "✅ MARCAR VERIFICAÇÃO",
                callback_data=f"verificarmenu_{conta_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "📜 HISTÓRICO",
                callback_data=f"historico_{conta_id}",
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


async def mostrar_menu_verificar(
    query,
    conta_id,
):
    await query.edit_message_text(
        "✅ *MARCAR VERIFICAÇÃO*\n\n"
        "Como está a conta?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ OK, funcionando",
                        callback_data=(
                            f"verificarresultado_{conta_id}_ok"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⚠️ Com problema",
                        callback_data=(
                            f"verificarresultado_{conta_id}_problema"
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


async def mostrar_historico_conta(
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

    historico = listar_historico_verificacoes(
        conta_id,
        limite=10,
    )

    if not historico:
        texto = (
            "📜 *HISTÓRICO DE VERIFICAÇÕES*\n\n"
            f"📦 {conta[1]}\n\n"
            "Nenhuma verificação registrada ainda."
        )
    else:
        texto = (
            "📜 *HISTÓRICO DE VERIFICAÇÕES*\n\n"
            f"📦 {conta[1]}\n\n"
        )

        for resultado, data in historico:

            emoji = (
                "✅" if resultado == "ok" else "⚠️"
            )

            texto += (
                f"{emoji} {str(data)[:16]} — "
                f"{'OK' if resultado == 'ok' else 'Problema'}\n"
            )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅️ Voltar",
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

NOMES_CAMPOS = {
    "servico": "Serviço",
    "email": "Email/login",
    "senha": "Senha",
    "data_criacao": "Data de criação",
    "data_vencimento": "Data de vencimento",
    "custo_criacao": "Custo de criação",
    "fornecedor": "Fornecedor",
    "telas_perfis": "Telas/perfis",
    "observacoes": "Observações",
    "tags": "Tags",
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
    elif campo == "data_vencimento":
        if not parse_data_br(texto):
            await update.message.reply_text(
                "❌ Data inválida. Use o formato "
                "DD/MM/AAAA (ex: 08/09/2026)."
            )
            return True
        valor = texto
    elif campo in CAMPOS_DATA and not parse_data_br(texto):
        await update.message.reply_text(
            "❌ Data inválida. Use o formato "
            "DD/MM/AAAA (ex: 08/09/2026)."
        )
        return True
    else:
        valor = texto

    # Ao editar o vencimento manualmente, zera o
    # controle de notificação pra evitar avisar de
    # novo antes da hora com a data antiga.
    if campo == "data_vencimento":
        marcar_vencimento_notificado(conta_id, "")

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


async def checar_vencimentos_proximos(
    bot,
):
    try:
        contas = listar_contas_com_vencimento()

        hoje = date.today()
        hoje_iso = hoje.isoformat()

        pendentes = []

        for (
            conta_id,
            servico,
            email,
            data_vencimento,
            notificado_em,
        ) in contas:

            data_venc_obj = parse_data_br(
                data_vencimento
            )

            if not data_venc_obj:
                continue

            dias_restantes = (
                data_venc_obj - hoje
            ).days

            if dias_restantes > DIAS_AVISO_VENCIMENTO:
                continue

            # já avisado hoje, não repete.
            if notificado_em == hoje_iso:
                continue

            pendentes.append(
                (
                    conta_id,
                    servico,
                    email,
                    dias_restantes,
                )
            )

        if not pendentes:
            return

        texto = (
            "⏰ *CONTAS PRA RENOVAR*\n\n"
        )

        botoes = []

        for (
            conta_id,
            servico,
            email,
            dias_restantes,
        ) in pendentes[:15]:

            rotulo = servico

            if email:
                rotulo += f" ({email[:20]})"

            if dias_restantes < 0:
                texto += (
                    f"🔴 {rotulo} — vencida há "
                    f"{abs(dias_restantes)} dia(s)\n"
                )
            elif dias_restantes == 0:
                texto += (
                    f"🟠 {rotulo} — vence hoje\n"
                )
            else:
                texto += (
                    f"🟡 {rotulo} — vence em "
                    f"{dias_restantes} dia(s)\n"
                )

            botoes.append(
                [
                    InlineKeyboardButton(
                        f"✏️ Atualizar: {servico[:25]}",
                        callback_data=(
                            f"editarcampo_{conta_id}"
                            f"_data_vencimento"
                        ),
                    )
                ]
            )

            marcar_vencimento_notificado(
                conta_id,
                hoje_iso,
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
            "ERRO NO VERIFICADOR DE VENCIMENTOS:",
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
            await checar_vencimentos_proximos(
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
            context,
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

    if acao == "categorias":
        await mostrar_categorias(
            query,
            context,
        )
        return

    if acao == "exportar_csv":
        await exportar_contas_csv(
            query,
            context,
        )
        return

    if acao == "filtrar_menu":
        await mostrar_menu_filtro(
            query,
            context,
        )
        return

    if acao == "filtrar_servico":
        await mostrar_filtro_servico(
            query,
            context,
        )
        return

    if acao == "filtrar_status":
        await mostrar_filtro_status(
            query,
            context,
        )
        return

    if acao.startswith("setfiltroservico_"):
        try:
            indice = int(
                acao.replace(
                    "setfiltroservico_", "", 1
                )
            )
            servicos = context.user_data.get(
                "servicos_disponiveis", []
            )
            context.user_data["filtro_servico"] = (
                servicos[indice]
            )
        except (ValueError, IndexError):
            await query.answer(
                "❌ Serviço inválido.",
                show_alert=True,
            )
            return

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

    if acao == "limpar_filtros":
        context.user_data.pop("filtro_servico", None)
        context.user_data.pop("filtro_status", None)

        await mostrar_lista_contas(
            query,
            context,
            1,
        )
        return

    if acao == "resumo_custos":
        await mostrar_resumo_custos(
            query,
            context,
        )
        return

    if acao == "lote_iniciar":
        await mostrar_confirmacao_lote(
            query,
            context,
        )
        return

    if acao == "lote_confirmar":
        await executar_lote(
            query,
            context,
        )
        return

    if acao.startswith("mostrarsenha_"):
        try:
            conta_id = int(
                acao.replace(
                    "mostrarsenha_", "", 1
                )
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
            mostrar_senha=True,
        )
        return

    if acao.startswith("ocultarsenha_"):
        try:
            conta_id = int(
                acao.replace(
                    "ocultarsenha_", "", 1
                )
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
            mostrar_senha=False,
        )
        return

    if acao.startswith("verificarmenu_"):
        try:
            conta_id = int(
                acao.replace(
                    "verificarmenu_", "", 1
                )
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await mostrar_menu_verificar(
            query,
            conta_id,
        )
        return

    if acao.startswith("verificarresultado_"):
        partes = acao.replace(
            "verificarresultado_", "", 1
        ).rsplit("_", 1)

        try:
            conta_id = int(partes[0])
            resultado = partes[1]
        except (ValueError, IndexError):
            await query.answer(
                "❌ Dados inválidos.",
                show_alert=True,
            )
            return

        marcar_conta_verificada(
            conta_id,
            resultado,
        )

        await query.answer(
            "✅ Verificação registrada!"
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
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await mostrar_historico_conta(
            query,
            conta_id,
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
