"""Configuration loaded from environment, never from committed credentials."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', '')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', '0') == '1'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_TIME_LIMIT = None
    BEHIND_PROXY = os.getenv('BEHIND_PROXY', '0') == '1'
    JSON_SORT_KEYS = False
