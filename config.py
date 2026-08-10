import os


# =========================================================
# CONFIGURAÃ‡Ã•ES (via variÃ¡veis de ambiente no Railway)
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
            "BOT_TOKEN nÃ£o configurado. "
            "Defina a variÃ¡vel de ambiente BOT_TOKEN."
        )

    if not ADMIN_ID:
        raise RuntimeError(
            "ADMIN_ID nÃ£o configurado. "
            "Defina a variÃ¡vel de ambiente ADMIN_ID "
            "com o seu ID numÃ©rico do Telegram."
        )

    print("âœ… ConfiguraÃ§Ã£o validada.")
