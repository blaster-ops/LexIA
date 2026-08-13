"""
Modelo de Ficha de Glosario para la base de datos (app/models/glossary.py).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class FichaGlosario(Base):
    """Modelo ORM para fichas del glosario jurídico en MySQL."""
    __tablename__ = "fichas_glosario"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    palabra = Column(String(255), index=True, nullable=False)
    definicion_tecnica = Column(Text, nullable=True)
    explicacion_sencilla = Column(Text, nullable=True)
    mnemotecnia = Column(Text, nullable=True)
    materia = Column(String(100), nullable=False)
    propietario = Column(String(100), index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<FichaGlosario(palabra='{self.palabra}', propietario='{self.propietario}')>"
