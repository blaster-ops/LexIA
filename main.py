"""
=============================================================================
Proyecto: LexIA - Asistente Jurídico Inteligente
Autor y Titular de Propiedad Intelectual: José Miguel Tapia Adán
Fecha de Creación: Mayo 2026
Institución: Universidad Tecnológica de Tehuacán (UTT)

Aviso Legal:
El presente código es una obra original. El acceso al mismo se otorga
exclusivamente para fines de evaluación académica. Queda estrictamente
prohibida su copia, modificación, distribución, o apropiación por parte 
de terceros sin autorización expresa.
=============================================================================
"""
# ── Protección crítica para ejecutables Windows (.exe) con PyInstaller ──
# DEBE ejecutarse antes de cualquier otra lógica de procesos.
import multiprocessing
multiprocessing.freeze_support()

# ── Forzar UTF-8 en stdout/stderr para evitar crash 'charmap' en Windows sin consola ──
import sys
import io
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import threading
import time
import logging
import uvicorn
import webview

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings, STATIC_DIR, DATA_DIR
from app.database import engine, Base, SessionLocal, asegurar_base_datos_existe
from app.models import Usuario
from app.crud import user_repository
from app.services import AuthService
from app.exceptions import (
    LexIAException,
    lexia_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)
from app.routers import auth_router, admin_router, glossary_router, rag_router

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lexia.main")

# --- INICIALIZACIÓN DE FASTAPI ---
app = FastAPI(
    title="LexIA: Asistente Jurídico Inteligente",
    version="2.0.0",
    description="Sistema enterprise de gestión jurídica y Tutor RAG con Ollama y MySQL."
)

# --- REGISTRO DE MANEJADORES DE EXCEPCIONALIDAD ---
app.add_exception_handler(LexIAException, lexia_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# --- INCLUSIÓN DE ROUTERS MODULARES ---
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(glossary_router)
app.include_router(rag_router)

# --- ARCHIVOS ESTÁTICOS Y RUTA PRINCIPAL ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def servir_inicio():
    """Servir la interfaz web principal del Despacho LexIA."""
    index_path = os.path.join(STATIC_DIR, "index_despacho.html")
    if not os.path.exists(index_path):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
    return FileResponse(index_path)

@app.on_event("startup")
def inicializar_aplicacion():
    """
    Garantiza que la base de datos MySQL exista, crea las tablas si no están creadas,
    y verifica/registra al usuario administrador inicial configurado en settings.
    """
    try:
        logger.info("Asegurando la existencia de la base de datos MySQL...")
        asegurar_base_datos_existe()

        logger.info("Inicializando esquema de tablas en MySQL...")
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            admin_username = settings.ADMIN_USERNAME.lower()
            admin_user = user_repository.get_by_username(db, admin_username)
            if not admin_user:
                logger.info(f"Creando usuario administrador inicial ('{admin_username}')...")
                hashed_pw = AuthService.get_password_hash(settings.ADMIN_PASSWORD)
                user_repository.create(db, username=admin_username, password_hash=hashed_pw, is_admin=True)
                
                # Crear carpetas del admin
                admin_dir = os.path.join(DATA_DIR, admin_username)
                os.makedirs(os.path.join(admin_dir, "uploads"), exist_ok=True)
                os.makedirs(os.path.join(admin_dir, "chroma_db"), exist_ok=True)
                logger.info(f"Administrador inicial '{admin_username}' registrado exitosamente.")
            else:
                logger.info(f"Usuario administrador principal ('{admin_username}') verificado.")
        finally:
            db.close()
    except Exception as e:
        logger.exception("Error crítico durante la inicialización de LexIA: %s", e)
        raise

def run_fastapi():
    """Arranca el servidor Uvicorn en un proceso/hilo secundario."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", reload=False, workers=1)

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # 1. Arrancar el servidor en un hilo secundario para no bloquear la UI
    server_thread = threading.Thread(target=run_fastapi, daemon=True)
    server_thread.start()

    # 2. Breve espera para inicializar Uvicorn
    time.sleep(1.5)

    # 3. Lanzar la ventana nativa pywebview
    logger.info("Lanzando ventana nativa LexIA...")
    ventana = webview.create_window(
        title="LexIA - Emerald Systems",
        url="http://127.0.0.1:8000",
        width=1280,
        height=800
    )
    webview.start()
