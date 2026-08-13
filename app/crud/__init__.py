"""
Módulo Repositorio/CRUD para operaciones directas en Base de Datos.
"""
from app.crud.user_crud import user_repository
from app.crud.glossary_crud import glossary_repository

__all__ = ["user_repository", "glossary_repository"]
