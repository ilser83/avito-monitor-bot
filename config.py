import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_БОТА")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
PROXY_URL = os.getenv("PROXY_URL", "")
PROXY_ROTATE_URL = os.getenv("PROXY_ROTATE_URL", "")
