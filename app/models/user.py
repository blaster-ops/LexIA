"""
Modelo de Usuario para la base de datos (app/models/user.py).
Incluye campos para Autenticación de Doble Factor (MFA / TOTP).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

class Usuario(Base):
    """Modelo ORM para usuarios en MySQL."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Usuario(username='{self.username}', is_admin={self.is_admin}, mfa_enabled={self.mfa_enabled})>"
