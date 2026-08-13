"""
Módulo de Manejo Centralizado de Excepciones (app/exceptions.py).
Define excepciones personalizadas y manejadores globales para respuestas HTTP semánticas.
"""
import logging
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("lexia.exceptions")

class LexIAException(Exception):
    """Excepción base para el sistema LexIA."""
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)

class OllamaServiceError(LexIAException):
    """Excepción lanzada cuando falla la comunicación con Ollama."""
    def __init__(self, detail: str = "Error de comunicación con el motor IA local (Ollama)"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

class RAGProcessingError(LexIAException):
    """Excepción lanzada durante fallos en la ingesta o búsqueda RAG."""
    def __init__(self, detail: str):
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)

async def lexia_exception_handler(request: Request, exc: LexIAException) -> JSONResponse:
    """Manejador para excepciones específicas de la aplicación."""
    logger.error(f"Excepción LexIA en {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_type": exc.__class__.__name__}
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Manejador para errores de Base de Datos (SQLAlchemy)."""
    logger.error(f"Error de Base de Datos en {request.url.path}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno en la base de datos.", "error_type": "DatabaseError"}
    )
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Manejador para errores de validación de entradas Pydantic."""
    logger.warning(f"Error de validación en {request.url.path}: {exc.errors()}")
    errors_serializable = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Datos de entrada inválidos.", "errors": errors_serializable}
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Manejador global para excepciones no capturadas (evita errores 500 silenciosos)."""
    logger.critical(f"Excepción no capturada en {request.url.path}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocurrió un error interno en el servidor.", "error_type": "InternalServerError"}
    )
