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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

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
            observacoes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        servico,
        email,
        senha,
        data_criacao,
        custo_criacao,
        fornecedor,
        telas_perfis,
        observacoes,
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
            criado_em
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
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contas
        SET ultima_verificacao = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        conta_id,
    ))

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


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
