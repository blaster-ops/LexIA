"""
Schemas Pydantic para Términos de Glosario (app/schemas/glossary.py).
"""
from pydantic import BaseModel, Field
from typing import Optional

class TerminoSchema(BaseModel):
    """Payload de entrada para agregar/editar un término jurídico."""
    palabra: str = Field(..., min_length=1, max_length=255, description="Término o concepto jurídico")
    definicion_tecnica: str = Field(default="", description="Definición formal técnica")
    explicacion_sencilla: str = Field(default="Pendiente de generación", description="Explicación didáctica")
    mnemotecnia: str = Field(default="Pendiente de generación", description="Regla mnemotécnica para memorizar")
    materia: str = Field(default="General", max_length=100, description="Materia jurídica (ej: Derecho Penal)")

class TerminoResponse(TerminoSchema):
    """Esquema de respuesta para términos de glosario."""
    id: Optional[int] = None
    propietario: Optional[str] = None
    existente: bool = False

    class Config:
        from_attributes = True
