"""
Repositorio CRUD para las fichas del Glosario Jurídico (app/crud/glossary_crud.py).
"""
from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.glossary import FichaGlosario

class GlossaryRepository:
    """Clase con métodos para gestionar las fichas del glosario en MySQL."""

    @staticmethod
    def get_by_palabra_and_propietario(db: Session, palabra: str, propietario: str) -> Optional[FichaGlosario]:
        """Obtiene una ficha por su palabra clave y propietario."""
        palabra_normalizada = palabra.strip().lower()
        return db.query(FichaGlosario).filter(
            func.lower(FichaGlosario.palabra) == palabra_normalizada,
            FichaGlosario.propietario == propietario
        ).first()

    @staticmethod
    def get_by_palabra_materia_and_propietario(
        db: Session,
        palabra: str,
        materia: str,
        propietario: str,
    ) -> Optional[FichaGlosario]:
        """Busca una ficha por la combinación normalizada de término, materia y propietario."""
        return db.query(FichaGlosario).filter(
            func.lower(func.trim(FichaGlosario.palabra)) == palabra.strip().lower(),
            func.lower(func.trim(FichaGlosario.materia)) == materia.strip().lower(),
            FichaGlosario.propietario == propietario,
        ).first()

    @staticmethod
    def search_by_propietario(
        db: Session,
        propietario: str,
        termino: str = "",
    ) -> List[FichaGlosario]:
        """Busca fichas del usuario por coincidencia parcial del término jurídico."""
        query = db.query(FichaGlosario).filter(FichaGlosario.propietario == propietario)
        termino_normalizado = termino.strip().lower()
        if termino_normalizado:
            query = query.filter(func.lower(FichaGlosario.palabra).contains(termino_normalizado))
        return query.order_by(FichaGlosario.palabra.asc(), FichaGlosario.materia.asc()).all()

    @staticmethod
    def get_by_id_and_propietario(db: Session, ficha_id: int, propietario: str) -> Optional[FichaGlosario]:
        """Obtiene una ficha concreta validando su propietario."""
        return db.query(FichaGlosario).filter(
            FichaGlosario.id == ficha_id,
            FichaGlosario.propietario == propietario,
        ).first()

    @staticmethod
    def get_by_palabra_any(db: Session, palabra: str) -> Optional[FichaGlosario]:
        """Busca una ficha por palabra sin importar el propietario."""
        return db.query(FichaGlosario).filter(FichaGlosario.palabra == palabra).first()

    @staticmethod
    def list_by_propietario(db: Session, propietario: str) -> List[FichaGlosario]:
        """Lista todas las fichas pertenecientes a un usuario específico."""
        return db.query(FichaGlosario).filter(FichaGlosario.propietario == propietario).all()

    @staticmethod
    def create(
        db: Session,
        palabra: str,
        definicion_tecnica: str,
        explicacion_sencilla: str,
        mnemotecnia: str,
        materia: str,
        propietario: str
    ) -> FichaGlosario:
        """Crea y guarda una nueva ficha de glosario."""
        ficha = FichaGlosario(
            palabra=palabra,
            definicion_tecnica=definicion_tecnica,
            explicacion_sencilla=explicacion_sencilla,
            mnemotecnia=mnemotecnia,
            materia=materia,
            propietario=propietario
        )
        db.add(ficha)
        db.commit()
        db.refresh(ficha)
        return ficha

    @staticmethod
    def update_content(
        db: Session,
        ficha: FichaGlosario,
        definicion_tecnica: str,
        explicacion_sencilla: str,
        mnemotecnia: str,
        materia: str,
    ) -> FichaGlosario:
        """Actualiza el contenido generado de una ficha existente."""
        ficha.definicion_tecnica = definicion_tecnica
        ficha.explicacion_sencilla = explicacion_sencilla
        ficha.mnemotecnia = mnemotecnia
        ficha.materia = materia
        db.commit()
        db.refresh(ficha)
        return ficha

    @staticmethod
    def delete(db: Session, ficha: FichaGlosario) -> None:
        """Elimina una ficha específica de la base de datos."""
        db.delete(ficha)
        db.commit()

    @staticmethod
    def delete_all_by_propietario(db: Session, propietario: str) -> int:
        """Elimina todas las fichas de un usuario determinado."""
        filas_borradas = db.query(FichaGlosario).filter(FichaGlosario.propietario == propietario).delete()
        db.commit()
        return filas_borradas

glossary_repository = GlossaryRepository()
