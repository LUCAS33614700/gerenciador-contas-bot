import os


# =========================================================
# CONFIGURAÇÕES (via variáveis de ambiente no Railway)
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
DATABASE_NAME = os.environ.get(
    "DATABASE_NAME",
    "contas.db",
)


def verificar_configuracao():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN não configurado. "
            "Defina a variável de ambiente BOT_TOKEN."
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "ADMIN_ID não configurado. "
            "Defina a variável de ambiente ADMIN_ID "
            "com o seu ID numérico do Telegram."
        )

    print("✅ Configuração validada.")
