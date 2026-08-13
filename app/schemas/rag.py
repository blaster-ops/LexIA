"""
Schemas Pydantic para el Sistema RAG y Búsquedas (app/schemas/rag.py).
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class BusquedaPDFResponse(BaseModel):
    """Respuesta para operaciones de búsqueda o ingesta PDF."""
    keyword: Optional[str] = None
    archivo: Optional[str] = None
    encontrado: Optional[bool] = None
    fragmento: Optional[str] = None
    documentos_extraidos: Optional[int] = None
    busqueda_realizada: bool = False
    mensaje: Optional[str] = None

class PreguntaTutorRequest(BaseModel):
    """Payload para realizar una consulta al Tutor IA."""
    pregunta: str = Field(..., min_length=2, description="Pregunta sobre el contenido jurídico o documentos")
    filename_filter: Optional[str] = Field(None, description="Filtro opcional por nombre de archivo PDF")

class PreguntaTutorResponse(BaseModel):
    """Respuesta generada por el Tutor IA."""
    respuesta: str
    fuentes: Optional[List[str]] = None

class ListaArchivosResponse(BaseModel):
    """Respuesta con la lista de archivos indexados en ChromaDB."""
    archivos: List[str]
