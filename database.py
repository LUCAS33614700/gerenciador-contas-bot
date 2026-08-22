import sqlite3

from config import DATABASE_NAME


# =========================================================
# CONEXÃO
# =========================================================

def conectar():
    return sqlite3.connect(DATABASE_NAME)


# =========================================================
# CRIAR TABELAS
# =========================================================

def criar_tabelas():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico TEXT NOT NULL,
            email TEXT,
            senha TEXT,
            data_criacao TEXT,
            custo_criacao REAL,
            fornecedor TEXT,
            telas_perfis TEXT,
            observacoes TEXT,
            status TEXT DEFAULT 'ativa',
            ultima_verificacao TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,
            criado_em TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # TAGS / RESULTADO DA VERIFICAÇÃO
    # -----------------------------------------------------

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN tags TEXT
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN ultimo_resultado_verificacao
            TEXT
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN contagem_problemas
            INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # VENCIMENTO / RENOVAÇÃO
    # -----------------------------------------------------

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN data_vencimento TEXT
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN vencimento_notificado_em
            TEXT
        """)
    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # DATA DA VENDA (CONTA INTEIRA)
    # -----------------------------------------------------

    try:
        cursor.execute("""
            ALTER TABLE contas
            ADD COLUMN data_venda TEXT
        """)
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS
        verificacoes_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conta_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # PERFIS/TELAS (COM CLIENTE)
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS perfis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conta_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            ocupado INTEGER DEFAULT 0,
            cliente_nome TEXT,
            cliente_contato TEXT,
            data_venda TEXT,
            observacoes TEXT,
            criado_em TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # VENCIMENTO AUTOMÁTICO DO PERFIL (30 DIAS APÓS VENDA)
    # -----------------------------------------------------

    try:
        cursor.execute("""
            ALTER TABLE perfis
            ADD COLUMN data_vencimento TEXT
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE perfis
            ADD COLUMN vencimento_notificado_em
            TEXT
        """)
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


# =========================================================
# CONFIGURAÇÕES (CHAVE / VALOR)
# =========================================================

def definir_configuracao(
    chave,
    valor,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO configuracoes
        (
            chave,
            valor
        )
        VALUES (?, ?)
        ON CONFLICT(chave)
        DO UPDATE SET valor = excluded.valor
    """, (
        chave,
        valor,
    ))

    conn.commit()
    conn.close()


def obter_configuracao(
    chave,
    padrao=None,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT valor
        FROM configuracoes
        WHERE chave = ?
    """, (
        chave,
    ))

    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        return resultado[0]

    return padrao


# =========================================================
# CONTAS - CRIAR / LISTAR / BUSCAR
# =========================================================

def cadastrar_conta(
    servico,
    email,
    senha,
    data_criacao,
    custo_criacao,
    fornecedor,
    telas_perfis,
    observacoes,
    tags=None,
    data_vencimento=None,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO contas
        (
            servico,
            email,
            senha,
            data_criacao,
            custo_criacao,
            fornecedor,
            telas_perfis,
            observacoes,
            tags,
            data_vencimento
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        servico,
        email,
        senha,
        data_criacao,
        custo_criacao,
        fornecedor,
        telas_perfis,
        observacoes,
        tags,
        data_vencimento,
    ))

    conta_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conta_id


def listar_contas(
    apenas_ativas=False,
):

    conn = conectar()
    cursor = conn.cursor()

    if apenas_ativas:

        cursor.execute("""
            SELECT
                id,
                servico,
                email,
                status
            FROM contas
            WHERE status = 'ativa'
            ORDER BY servico, id
        """)

    else:

        cursor.execute("""
            SELECT
                id,
                servico,
                email,
                status
            FROM contas
            ORDER BY servico, id
        """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def listar_contas_filtrado(
    servico=None,
    status=None,
    tag=None,
):

    conn = conectar()
    cursor = conn.cursor()

    condicoes = []
    parametros = []

    if servico:
        condicoes.append("servico = ?")
        parametros.append(servico)

    if status:
        condicoes.append("status = ?")
        parametros.append(status)

    if tag:
        condicoes.append(
            "tags LIKE ? COLLATE NOCASE"
        )
        parametros.append(f"%{tag}%")

    where = (
        "WHERE " + " AND ".join(condicoes)
        if condicoes
        else ""
    )

    cursor.execute(
        f"""
        SELECT
            id,
            servico,
            email,
            status
        FROM contas
        {where}
        ORDER BY servico, id
        """,
        parametros,
    )

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def listar_servicos_distintos():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT servico
        FROM contas
        ORDER BY servico
    """)

    resultados = cursor.fetchall()

    conn.close()

    return [linha[0] for linha in resultados]


def listar_tags_distintas():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tags
        FROM contas
        WHERE tags IS NOT NULL
        AND tags != ''
    """)

    resultados = cursor.fetchall()

    conn.close()

    tags_unicas = set()

    for linha in resultados:

        partes = (linha[0] or "").split(",")

        for parte in partes:

            tag_limpa = parte.strip()

            if tag_limpa:
                tags_unicas.add(tag_limpa)

    return sorted(tags_unicas)


def buscar_conta(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
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
            ultimo_resultado_verificacao,
            contagem_problemas,
            data_vencimento,
            vencimento_notificado_em,
            data_venda
        FROM contas
        WHERE id = ?
    """, (
        conta_id,
    ))

    resultado = cursor.fetchone()

    conn.close()

    return resultado


def buscar_contas_por_termo(
    termo,
):

    conn = conectar()
    cursor = conn.cursor()

    termo_like = f"%{termo}%"

    cursor.execute("""
        SELECT
            id,
            servico,
            email,
            status
        FROM contas
        WHERE servico LIKE ? COLLATE NOCASE
        OR email LIKE ? COLLATE NOCASE
        OR fornecedor LIKE ? COLLATE NOCASE
        ORDER BY servico, id
    """, (
        termo_like,
        termo_like,
        termo_like,
    ))

    resultados = cursor.fetchall()

    conn.close()

    return resultados


# =========================================================
# CONTAS - ATUALIZAR CAMPOS
# =========================================================

CAMPOS_EDITAVEIS = {
    "servico": "servico",
    "email": "email",
    "senha": "senha",
    "data_criacao": "data_criacao",
    "custo_criacao": "custo_criacao",
    "fornecedor": "fornecedor",
    "telas_perfis": "telas_perfis",
    "observacoes": "observacoes",
    "tags": "tags",
    "data_vencimento": "data_vencimento",
}


def atualizar_campo_conta(
    conta_id,
    campo,
    valor,
):

    if campo not in CAMPOS_EDITAVEIS:
        raise ValueError(
            f"Campo inválido: {campo}"
        )

    coluna = CAMPOS_EDITAVEIS[campo]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        UPDATE contas
        SET {coluna} = ?
        WHERE id = ?
        """,
        (
            valor,
            conta_id,
        ),
    )

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def definir_status_conta(
    conta_id,
    status,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contas
        SET status = ?
        WHERE id = ?
    """, (
        status,
        conta_id,
    ))

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def marcar_conta_verificada(
    conta_id,
    resultado="ok",
):

    conn = conectar()
    cursor = conn.cursor()

    if resultado == "problema":

        cursor.execute("""
            UPDATE contas
            SET ultima_verificacao = CURRENT_TIMESTAMP,
                ultimo_resultado_verificacao = ?,
                contagem_problemas = contagem_problemas + 1
            WHERE id = ?
        """, (
            resultado,
            conta_id,
        ))

    else:

        cursor.execute("""
            UPDATE contas
            SET ultima_verificacao = CURRENT_TIMESTAMP,
                ultimo_resultado_verificacao = ?
            WHERE id = ?
        """, (
            resultado,
            conta_id,
        ))

    alterado = cursor.rowcount > 0

    if alterado:

        cursor.execute("""
            INSERT INTO verificacoes_historico
            (
                conta_id,
                resultado
            )
            VALUES (?, ?)
        """, (
            conta_id,
            resultado,
        ))

    conn.commit()
    conn.close()

    return alterado


def listar_historico_verificacoes(
    conta_id,
    limite=5,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            resultado,
            data
        FROM verificacoes_historico
        WHERE conta_id = ?
        ORDER BY data DESC
        LIMIT ?
    """, (
        conta_id,
        limite,
    ))

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def excluir_conta(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM contas
        WHERE id = ?
    """, (
        conta_id,
    ))

    excluido = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return excluido


# =========================================================
# VERIFICAÇÃO PERIÓDICA
# =========================================================

def listar_contas_para_verificar(
    intervalo_dias,
):
    """
    Retorna as contas ativas cuja última
    verificação foi há mais dias do que o
    intervalo definido.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            servico,
            email,
            ultima_verificacao
        FROM contas
        WHERE status = 'ativa'
        AND julianday('now')
            - julianday(ultima_verificacao)
            >= ?
        ORDER BY ultima_verificacao
    """, (
        intervalo_dias,
    ))

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def contar_contas():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(CASE WHEN status = 'ativa' THEN 1 ELSE 0 END)
        FROM contas
    """)

    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        total = int(resultado[0] or 0)
        ativas = int(resultado[1] or 0)
        return total, ativas

    return 0, 0


# =========================================================
# RESUMO DE CUSTOS
# =========================================================

def obter_resumo_custos():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(custo_criacao), 0),
            COALESCE(SUM(
                CASE WHEN status = 'ativa'
                THEN custo_criacao ELSE 0 END
            ), 0),
            COUNT(
                CASE WHEN custo_criacao IS NOT NULL
                THEN 1 END
            )
        FROM contas
    """)

    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        return (
            float(resultado[0] or 0),
            float(resultado[1] or 0),
            int(resultado[2] or 0),
        )

    return 0.0, 0.0, 0


def obter_custo_por_servico():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            servico,
            COALESCE(SUM(custo_criacao), 0),
            COUNT(*)
        FROM contas
        GROUP BY servico
        ORDER BY SUM(custo_criacao) DESC
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


# =========================================================
# VERIFICAÇÃO EM LOTE
# =========================================================

def verificar_todas_pendentes(
    intervalo_dias,
    resultado="ok",
):
    """
    Marca como verificadas (com o resultado
    informado) todas as contas ativas que
    estão vencidas no intervalo de checagem.
    Retorna quantas foram marcadas.
    """

    pendentes = listar_contas_para_verificar(
        intervalo_dias
    )

    for conta in pendentes:

        conta_id = conta[0]

        marcar_conta_verificada(
            conta_id,
            resultado,
        )

    return len(pendentes)


# =========================================================
# CATEGORIAS (SERVIÇO)
# =========================================================

def contar_contas_por_servico():
    """
    Retorna, por serviço (categoria), o total de
    contas cadastradas e quantas estão ativas.
    Ex: [("Netflix", 5, 4), ("Disney+", 2, 2)]
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            servico,
            COUNT(*),
            SUM(CASE WHEN status = 'ativa' THEN 1 ELSE 0 END)
        FROM contas
        GROUP BY servico
        ORDER BY servico
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


# =========================================================
# VENCIMENTO / RENOVAÇÃO
# =========================================================

def listar_contas_com_vencimento():
    """
    Retorna todas as contas ativas que têm uma
    data de vencimento cadastrada. O cálculo de
    quantos dias faltam é feito em Python, já que
    a data é guardada como texto (DD/MM/AAAA).
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            servico,
            email,
            data_vencimento,
            vencimento_notificado_em
        FROM contas
        WHERE status = 'ativa'
        AND data_vencimento IS NOT NULL
        AND data_vencimento != ''
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def marcar_vencimento_notificado(
    conta_id,
    data_notificacao,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contas
        SET vencimento_notificado_em = ?
        WHERE id = ?
    """, (
        data_notificacao,
        conta_id,
    ))

    conn.commit()
    conn.close()


def marcar_conta_vendida(
    conta_id,
    data_venda,
    data_vencimento,
):
    """
    Registra a data em que a conta (inteira) foi
    vendida e já define o vencimento automático
    (normalmente venda + 30 dias), sem apagar
    nenhum outro dado da conta. Zera o aviso de
    vencimento já enviado, pra recontar o prazo.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contas
        SET data_venda = ?,
            data_vencimento = ?,
            vencimento_notificado_em = NULL
        WHERE id = ?
    """, (
        data_venda,
        data_vencimento,
        conta_id,
    ))

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def listar_perfis_com_vencimento():
    """
    Retorna todos os perfis/telas ocupados (vendidos)
    que têm vencimento automático calculado, junto
    com o serviço da conta a que pertencem.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            perfis.id,
            perfis.nome,
            perfis.conta_id,
            contas.servico,
            perfis.cliente_nome,
            perfis.data_vencimento,
            perfis.vencimento_notificado_em
        FROM perfis
        JOIN contas ON contas.id = perfis.conta_id
        WHERE perfis.ocupado = 1
        AND perfis.data_vencimento IS NOT NULL
        AND perfis.data_vencimento != ''
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def marcar_vencimento_perfil_notificado(
    perfil_id,
    data_notificacao,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE perfis
        SET vencimento_notificado_em = ?
        WHERE id = ?
    """, (
        data_notificacao,
        perfil_id,
    ))

    conn.commit()
    conn.close()


# =========================================================
# EXPORTAÇÃO (CSV)
# =========================================================

def obter_todas_contas_para_exportar():
    """
    Retorna todas as contas com todos os campos,
    prontas pra serem escritas num CSV.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            servico,
            email,
            senha,
            data_criacao,
            data_vencimento,
            custo_criacao,
            fornecedor,
            telas_perfis,
            tags,
            observacoes,
            status,
            ultima_verificacao,
            criado_em,
            data_venda
        FROM contas
        ORDER BY servico, id
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


# =========================================================
# IMPORTAÇÃO (CSV DE BACKUP)
# =========================================================

def existe_conta_igual(
    servico,
    email,
):
    """
    Checagem simples de duplicidade pra importação
    de CSV: considera "igual" quando serviço e email
    batem exatamente.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM contas
        WHERE servico = ?
        AND IFNULL(email, '') = IFNULL(?, '')
        LIMIT 1
    """, (
        servico,
        email,
    ))

    resultado = cursor.fetchone()

    conn.close()

    return resultado[0] if resultado else None


def importar_conta_completa(dados):
    """
    Insere uma conta a partir de um CSV de backup,
    preservando status, vencimento e data de venda
    (diferente de cadastrar_conta, feita pro fluxo
    manual de cadastro). Não recebe nem sobrescreve
    nenhuma conta já existente — sempre cria uma
    linha nova.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO contas
        (
            servico,
            email,
            senha,
            data_criacao,
            custo_criacao,
            fornecedor,
            telas_perfis,
            observacoes,
            tags,
            data_vencimento,
            status,
            data_venda
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dados.get("servico"),
        dados.get("email"),
        dados.get("senha"),
        dados.get("data_criacao"),
        dados.get("custo_criacao") or None,
        dados.get("fornecedor"),
        dados.get("telas_perfis"),
        dados.get("observacoes"),
        dados.get("tags"),
        dados.get("data_vencimento"),
        dados.get("status") or "ativa",
        dados.get("data_venda"),
    ))

    novo_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return novo_id


# =========================================================
# PERFIS/TELAS (COM CLIENTE)
# =========================================================

def cadastrar_perfil(
    conta_id,
    nome,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO perfis
        (
            conta_id,
            nome
        )
        VALUES (?, ?)
    """, (
        conta_id,
        nome,
    ))

    perfil_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return perfil_id


def listar_perfis(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            nome,
            ocupado,
            cliente_nome,
            cliente_contato,
            data_venda,
            observacoes,
            data_vencimento
        FROM perfis
        WHERE conta_id = ?
        ORDER BY id
    """, (
        conta_id,
    ))

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def buscar_perfil(
    perfil_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            conta_id,
            nome,
            ocupado,
            cliente_nome,
            cliente_contato,
            data_venda,
            observacoes,
            data_vencimento,
            vencimento_notificado_em
        FROM perfis
        WHERE id = ?
    """, (
        perfil_id,
    ))

    resultado = cursor.fetchone()

    conn.close()

    return resultado


def atualizar_perfil(
    perfil_id,
    ocupado=None,
    cliente_nome=None,
    cliente_contato=None,
    data_venda=None,
    observacoes=None,
    data_vencimento=None,
):
    """
    Atualiza os campos de um perfil. Passar None
    num campo significa "não alterar" — exceto
    ocupado, que é sempre definido quando informado
    como 0 ou 1.
    """

    conn = conectar()
    cursor = conn.cursor()

    campos = []
    valores = []

    if ocupado is not None:
        campos.append("ocupado = ?")
        valores.append(ocupado)

    if cliente_nome is not None:
        campos.append("cliente_nome = ?")
        valores.append(cliente_nome)

    if cliente_contato is not None:
        campos.append("cliente_contato = ?")
        valores.append(cliente_contato)

    if data_venda is not None:
        campos.append("data_venda = ?")
        valores.append(data_venda)

    if observacoes is not None:
        campos.append("observacoes = ?")
        valores.append(observacoes)

    if data_vencimento is not None:
        campos.append("data_vencimento = ?")
        valores.append(data_vencimento)
        campos.append("vencimento_notificado_em = NULL")

    if not campos:
        conn.close()
        return False

    valores.append(perfil_id)

    cursor.execute(
        f"""
        UPDATE perfis
        SET {', '.join(campos)}
        WHERE id = ?
        """,
        valores,
    )

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def liberar_perfil(
    perfil_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE perfis
        SET ocupado = 0,
            cliente_nome = NULL,
            cliente_contato = NULL,
            data_venda = NULL,
            observacoes = NULL,
            data_vencimento = NULL,
            vencimento_notificado_em = NULL
        WHERE id = ?
    """, (
        perfil_id,
    ))

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def excluir_perfil(
    perfil_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM perfis
        WHERE id = ?
    """, (
        perfil_id,
    ))

    excluido = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return excluido


# =========================================================
# DUPLICAR CONTA
# =========================================================

def duplicar_conta(
    conta_id,
    novo_email=None,
    nova_senha=None,
):
    """
    Cria uma nova conta copiando todos os campos
    de uma existente, exceto email e senha (se
    novos valores forem informados).
    """

    original = buscar_conta(conta_id)

    if not original:
        return None

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
        _status,
        _ultima_verificacao,
        _criado_em,
        tags,
        _ultimo_resultado,
        _contagem_problemas,
        data_vencimento,
        _vencimento_notificado_em,
    ) = original

    return cadastrar_conta(
        servico=servico,
        email=novo_email if novo_email else email,
        senha=nova_senha if nova_senha else senha,
        data_criacao=data_criacao,
        custo_criacao=custo_criacao,
        fornecedor=fornecedor,
        telas_perfis=telas_perfis,
        observacoes=observacoes,
        tags=tags,
        data_vencimento=data_vencimento,
    )
