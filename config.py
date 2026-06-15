import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-key")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
    SCHEDULER_INTERVAL_MINUTES = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", 60))
    SMTP_SENDER = os.getenv("SMTP_SENDER", "")
    SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
