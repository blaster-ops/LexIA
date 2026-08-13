"""
Repositorio CRUD para la entidad Usuario (app/crud/user_crud.py).
Encapsula todas las operaciones de lectura/escritura en la base de datos MySQL.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.user import Usuario

class UserRepository:
    """Clase con métodos estáticos para gestionar usuarios en la DB."""

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[Usuario]:
        """Obtiene un usuario por su nombre de usuario (case-insensitive)."""
        return db.query(Usuario).filter(Usuario.username == username.lower()).first()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[Usuario]:
        """Obtiene un usuario por su ID primario."""
        return db.query(Usuario).filter(Usuario.id == user_id).first()

    @staticmethod
    def list_all(db: Session) -> List[Usuario]:
        """Devuelve la lista de todos los usuarios registrados."""
        return db.query(Usuario).all()

    @staticmethod
    def count(db: Session) -> int:
        """Devuelve el total de usuarios registrados."""
        return db.query(Usuario).count()

    @staticmethod
    def create(db: Session, username: str, password_hash: str, is_admin: bool = False) -> Usuario:
        """Crea un nuevo registro de usuario."""
        nuevo_usuario = Usuario(
            username=username.lower(),
            password_hash=password_hash,
            is_admin=is_admin,
            mfa_enabled=False
        )
        db.add(nuevo_usuario)
        try:
            db.commit()
            db.refresh(nuevo_usuario)
            return nuevo_usuario
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def set_mfa_secret(db: Session, user: Usuario, secret: str) -> None:
        """Establece la clave secreta TOTP temporal/definitiva del usuario."""
        user.mfa_secret = secret
        db.commit()

    @staticmethod
    def enable_mfa(db: Session, user: Usuario, secret: str) -> None:
        """Habilita la autenticación de doble factor (MFA) para el usuario."""
        user.mfa_secret = secret
        user.mfa_enabled = True
        db.commit()

    @staticmethod
    def disable_mfa(db: Session, user: Usuario) -> None:
        """Deshabilita el doble factor (MFA) para el usuario."""
        user.mfa_secret = None
        user.mfa_enabled = False
        db.commit()

    @staticmethod
    def delete(db: Session, user: Usuario) -> None:
        """Elimina un usuario de la base de datos."""
        db.delete(user)
        db.commit()

user_repository = UserRepository()
