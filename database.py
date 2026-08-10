import sqlite3

from config import DATABASE_NAME


# =========================================================
# CONEXÃƒO
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
                DEFAULT CURRENT_TIMESTAMP,
            tags TEXT DEFAULT ''
        )
    """)

    # MigraÃ§Ã£o: bancos criados antes da versÃ£o com tags
    # nÃ£o tÃªm essa coluna â€” adiciona se faltar.
    cursor.execute("PRAGMA table_info(contas)")
    colunas_existentes = {
        linha[1] for linha in cursor.fetchall()
    }

    if "tags" not in colunas_existentes:
        cursor.execute(
            "ALTER TABLE contas ADD COLUMN tags TEXT DEFAULT ''"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_verificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conta_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conta_id) REFERENCES contas(id)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# CONFIGURAÃ‡Ã•ES (CHAVE / VALOR)
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
            tags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        servico,
        email,
        senha,
        data_criacao,
        custo_criacao,
        fornecedor,
        telas_perfis,
        observacoes,
        tags or "",
    ))

    conta_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conta_id


def listar_contas(
    apenas_ativas=False,
    servico=None,
    status=None,
    tag=None,
):
    """
    Lista contas (id, servico, email, status), com
    filtros opcionais por serviÃ§o, status e/ou tag.
    `apenas_ativas` tem prioridade sobre `status` por
    compatibilidade com chamadas antigas.
    """

    conn = conectar()
    cursor = conn.cursor()

    condicoes = []
    parametros = []

    if apenas_ativas:
        condicoes.append("status = 'ativa'")
    elif status:
        condicoes.append("status = ?")
        parametros.append(status)

    if servico:
        condicoes.append("servico = ?")
        parametros.append(servico)

    if tag:
        condicoes.append("tags LIKE ? COLLATE NOCASE")
        parametros.append(f"%{tag}%")

    where = ""
    if condicoes:
        where = "WHERE " + " AND ".join(condicoes)

    cursor.execute(f"""
        SELECT
            id,
            servico,
            email,
            status
        FROM contas
        {where}
        ORDER BY servico, id
    """, parametros)

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

    resultados = [
        linha[0] for linha in cursor.fetchall()
    ]

    conn.close()

    return resultados


def listar_tags_distintas():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tags
        FROM contas
        WHERE tags IS NOT NULL AND tags != ''
    """)

    linhas = cursor.fetchall()

    conn.close()

    tags = set()

    for (valor,) in linhas:
        for parte in valor.split(","):
            parte = parte.strip()
            if parte:
                tags.add(parte)

    return sorted(tags)


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
            tags
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
        OR tags LIKE ? COLLATE NOCASE
        ORDER BY servico, id
    """, (
        termo_like,
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
}


def atualizar_campo_conta(
    conta_id,
    campo,
    valor,
):

    if campo not in CAMPOS_EDITAVEIS:
        raise ValueError(
            f"Campo invÃ¡lido: {campo}"
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
    """
    Marca a conta como verificada agora e registra o
    resultado ("ok" ou "problema") no histÃ³rico.
    """

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

    cursor.execute("""
        INSERT INTO historico_verificacoes
        (conta_id, resultado)
        VALUES (?, ?)
    """, (
        conta_id,
        resultado,
    ))

    conn.commit()
    conn.close()

    return alterado


def marcar_varias_verificadas(
    conta_ids,
    resultado="ok",
):
    """
    Marca vÃ¡rias contas como verificadas de uma vez,
    todas com o mesmo resultado. Retorna quantas foram
    de fato atualizadas.
    """

    if not conta_ids:
        return 0

    conn = conectar()
    cursor = conn.cursor()

    marcadas = 0

    for conta_id in conta_ids:

        cursor.execute("""
            UPDATE contas
            SET ultima_verificacao = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            conta_id,
        ))

        if cursor.rowcount > 0:
            marcadas += 1

        cursor.execute("""
            INSERT INTO historico_verificacoes
            (conta_id, resultado)
            VALUES (?, ?)
        """, (
            conta_id,
            resultado,
        ))

    conn.commit()
    conn.close()

    return marcadas


def obter_ultima_verificacao_resultado(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT resultado, data
        FROM historico_verificacoes
        WHERE conta_id = ?
        ORDER BY data DESC
        LIMIT 1
    """, (
        conta_id,
    ))

    resultado = cursor.fetchone()

    conn.close()

    return resultado


def listar_historico_verificacoes(
    conta_id,
    limite=10,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT resultado, data
        FROM historico_verificacoes
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
        DELETE FROM historico_verificacoes
        WHERE conta_id = ?
    """, (
        conta_id,
    ))

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
# VERIFICAÃ‡ÃƒO PERIÃ“DICA
# =========================================================

def listar_contas_para_verificar(
    intervalo_dias,
):
    """
    Retorna as contas ativas cuja Ãºltima
    verificaÃ§Ã£o foi hÃ¡ mais dias do que o
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

def resumo_custos():
    """
    Retorna um dicionÃ¡rio com o total investido na
    criaÃ§Ã£o das contas (soma de custo_criacao),
    separado por status.
    """

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*),
            COUNT(CASE WHEN custo_criacao IS NOT NULL THEN 1 END),
            SUM(custo_criacao),
            SUM(CASE WHEN status = 'ativa'
                THEN custo_criacao ELSE 0 END),
            SUM(CASE WHEN status != 'ativa'
                THEN custo_criacao ELSE 0 END)
        FROM contas
    """)

    resultado = cursor.fetchone()

    conn.close()

    return {
        "total_contas": int(resultado[0] or 0),
        "contas_com_custo": int(resultado[1] or 0),
        "total_gasto": float(resultado[2] or 0),
        "gasto_ativas": float(resultado[3] or 0),
        "gasto_inativas": float(resultado[4] or 0),
    }
