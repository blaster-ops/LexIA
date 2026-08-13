"""
Módulo de Acceso a Base de Datos (app/database.py).
Gestiona el motor SQLAlchemy para MySQL de forma totalmente estática y perezosa (lazy).
No intenta ninguna conexión al ser importado.
"""
from typing import Generator
import re

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.config import settings

# Construir URL de conexión para MySQL usando PyMySQL
MYSQL_DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
    query={"charset": "utf8mb4"},
)

# Motor SQLAlchemy creado perezosamente (lazy) sin intentar conexión al importar
engine = create_engine(
    MYSQL_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False
)

# Fábrica de sesiones y clase base declarativa para modelos ORM
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def asegurar_base_datos_existe() -> None:
    """Garantiza que la base de datos MySQL configurada (lexia_db) exista en el servidor."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", settings.DB_NAME):
        raise ValueError("DB_NAME solo puede contener letras, números y guiones bajos.")

    import pymysql
    connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            charset="utf8mb4",
            connect_timeout=10,
        )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        connection.commit()
    finally:
        connection.close()

def get_db() -> Generator[Session, None, None]:
    """
    Inyector de dependencia para FastAPI que proporciona una sesión de base de datos
    y la cierra automáticamente al finalizar el request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
