# config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # SFTP конфигурация
    SFTP_HOST = os.environ.get('SFTP_HOST') or 'localhost'
    SFTP_PORT = int(os.environ.get('SFTP_PORT') or 22)
    SFTP_USERNAME = os.environ.get('SFTP_USERNAME') or 'username'
    SFTP_PASSWORD = os.environ.get('SFTP_PASSWORD') or 'password'

    # Для использования SSH ключа вместо пароля
    SFTP_KEY_FILENAME = os.environ.get('SFTP_KEY_FILENAME')  # путь к приватному ключу

    # Сессии
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 час