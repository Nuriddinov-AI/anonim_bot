import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
SECRET_KEY = os.getenv("SECRET_KEY", "users_info")
