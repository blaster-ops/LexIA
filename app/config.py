"""
Módulo de Configuración de la Aplicación (app/config.py).
Gestiona y valida todas las variables de entorno mediante Pydantic Settings.
"""
import os
import sys
import logging
import secrets
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field

    class Settings(BaseSettings):
        """Configuración centralizada cargada desde variables de entorno (.env)."""
        # Base de Datos MySQL
        DB_HOST: str = Field(default="localhost", env="DB_HOST")
        DB_PORT: int = Field(default=3306, env="DB_PORT")
        DB_USER: str = Field(default="root", env="DB_USER")
        DB_PASSWORD: str = Field(default="", env="DB_PASSWORD")
        DB_NAME: str = Field(default="lexia_db", env="DB_NAME")
        
        # Seguridad y JWT
        ADMIN_USERNAME: str = Field(default="2eigth", env="ADMIN_USERNAME")
        ADMIN_PASSWORD: str = Field(default="", env="ADMIN_PASSWORD")
        LEXIA_SECRET_KEY: str = Field(default="cambia_esto_por_una_clave_secreta_muy_larga_y_aleatoria", env="LEXIA_SECRET_KEY")
        JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
        ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="ACCESS_TOKEN_EXPIRE_MINUTES")

        # Integración Ollama y RAG
        OLLAMA_URL: str = Field(default="http://localhost:11434", env="OLLAMA_URL")
        OLLAMA_MODEL: str = Field(default="gemma:7b", env="OLLAMA_MODEL")
        OLLAMA_TIMEOUT: float = Field(default=120.0, env="OLLAMA_TIMEOUT")
        MAX_UPLOAD_SIZE_MB: int = Field(default=50, ge=1, le=500, env="MAX_UPLOAD_SIZE_MB")

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

except ImportError:
    # Fallback si pydantic-settings aún no está instalado en el entorno ejecutor
    from dotenv import load_dotenv
    load_dotenv()

    class Settings:
        DB_HOST: str = os.getenv("DB_HOST", "localhost")
        DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
        DB_USER: str = os.getenv("DB_USER", "root")
        DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
        DB_NAME: str = os.getenv("DB_NAME", "lexia_db")
        
        ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "2eigth")
        ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
        LEXIA_SECRET_KEY: str = os.getenv("LEXIA_SECRET_KEY", "cambia_esto_por_una_clave_secreta_muy_larga_y_aleatoria")
        JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

        OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma:7b")
        OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))
        MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

settings = Settings()

# Nunca firmar JWT con la clave pública de ejemplo. En ausencia de una clave
# configurada se genera una clave efímera segura (las sesiones expiran al reiniciar).
_INSECURE_DEFAULT_SECRET = "cambia_esto_por_una_clave_secreta_muy_larga_y_aleatoria"
if settings.LEXIA_SECRET_KEY == _INSECURE_DEFAULT_SECRET:
    settings.LEXIA_SECRET_KEY = secrets.token_urlsafe(48)
    logging.getLogger("lexia.config").warning(
        "LEXIA_SECRET_KEY no está configurada: se usará una clave segura efímera. "
        "Define una clave estable en .env para conservar sesiones entre reinicios."
    )

# Resolución de Directorios Base (soporta PyInstaller .exe y entorno de desarrollo .py)
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    APP_DIR = BASE_DIR

STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(APP_DIR, "data", "users")
os.makedirs(DATA_DIR, exist_ok=True)
