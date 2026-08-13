"""
Módulo de Schemas Pydantic para Validación de Datos y Respuestas HTTP.
"""
from app.schemas.user import (
    UsuarioCreate, UsuarioResponse, Token, TokenData,
    MFASetupResponse, MFAVerifyRequest, MFALoginRequest
)
from app.schemas.glossary import TerminoSchema, TerminoResponse
from app.schemas.rag import BusquedaPDFResponse, PreguntaTutorRequest, PreguntaTutorResponse, ListaArchivosResponse

__all__ = [
    "UsuarioCreate", "UsuarioResponse", "Token", "TokenData",
    "MFASetupResponse", "MFAVerifyRequest", "MFALoginRequest",
    "TerminoSchema", "TerminoResponse",
    "BusquedaPDFResponse", "PreguntaTutorRequest", "PreguntaTutorResponse", "ListaArchivosResponse"
]

