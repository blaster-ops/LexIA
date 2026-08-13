"""
Router de Administración (app/routers/admin.py).
Gestiona la creación, listado y eliminación de usuarios (solo accesible para el Administrador).
"""
import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import user_repository
from app.services import AuthService, get_current_user
from app.schemas import UsuarioCreate
from app.config import DATA_DIR, settings

router = APIRouter(prefix="/admin", tags=["Administración"])

def verificar_admin(db: Session, username: str) -> None:
    """Verifica si el usuario actual posee permisos de administrador."""
    user = user_repository.get_by_username(db, username)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Se requieren permisos de administrador."
        )

@router.post("/crear_usuario", response_model=dict, summary="Crear un nuevo usuario")
def crear_usuario(
    user_data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Crea un nuevo usuario en la base de datos MySQL e inicializa sus directorios físicos."""
    verificar_admin(db, current_user)

    username_lower = user_data.username.lower()
    if user_repository.get_by_username(db, username_lower):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre de usuario '{username_lower}' ya existe en el sistema."
        )

    hashed_pw = AuthService.get_password_hash(user_data.password)
    try:
        user_repository.create(db, username=username_lower, password_hash=hashed_pw, is_admin=False)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre de usuario '{username_lower}' ya existe en el sistema."
        )

    # Crear estructura física de directorios aislados por usuario
    user_dir = os.path.join(DATA_DIR, username_lower)
    os.makedirs(os.path.join(user_dir, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(user_dir, "chroma_db"), exist_ok=True)

    return {"mensaje": f"Usuario '{username_lower}' creado exitosamente."}

@router.get("/usuarios", response_model=List[dict], summary="Listar todos los usuarios")
def listar_usuarios(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> List[dict]:
    """Retorna la lista de todos los usuarios registrados con su rol."""
    verificar_admin(db, current_user)
    usuarios = user_repository.list_all(db)
    return [{"username": u.username, "is_admin": u.is_admin, "mfa_enabled": u.mfa_enabled} for u in usuarios]

@router.delete("/borrar_usuario/{username}", response_model=dict, summary="Eliminar un usuario")
def borrar_usuario(
    username: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Elimina un usuario de MySQL y destruye sus archivos físicos almacenados."""
    verificar_admin(db, current_user)

    target_user = username.lower()
    if target_user == settings.ADMIN_USERNAME.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No es posible eliminar al administrador principal del sistema."
        )

    db_user = user_repository.get_by_username(db, target_user)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el usuario '{target_user}'."
        )

    user_repository.delete(db, db_user)

    # Limpiar directorios del usuario
    user_dir = os.path.join(DATA_DIR, target_user)
    if os.path.exists(user_dir):
        try:
            shutil.rmtree(user_dir)
        except Exception as e:
            pass

    return {"mensaje": f"Usuario '{target_user}' y sus archivos fueron eliminados correctamente."}
