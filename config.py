import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8557470388"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "")
