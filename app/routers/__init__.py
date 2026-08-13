"""
Módulo de Routers de FastAPI para LexIA.
"""
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.glossary import router as glossary_router
from app.routers.rag import router as rag_router

__all__ = ["auth_router", "admin_router", "glossary_router", "rag_router"]
