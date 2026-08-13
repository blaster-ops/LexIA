"""
Schemas Pydantic para Autenticación, Gestión de Usuarios y MFA (app/schemas/user.py).
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

import re

class UsuarioCreate(BaseModel):
    """Payload para registro o creación de usuarios."""
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único")
    password: str = Field(..., min_length=6, max_length=100, description="Contraseña del usuario")

    @field_validator("username")
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_]{3,50}$", v):
            raise ValueError("El nombre de usuario solo puede contener letras, números y guiones bajos (sin espacios ni caracteres especiales).")
        return v

class UsuarioResponse(BaseModel):
    """Esquema de respuesta para información de usuario."""
    id: int
    username: str
    is_admin: bool
    mfa_enabled: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    """Respuesta con Token de Acceso JWT o estado de MFA requerido."""
    access_token: Optional[str] = None
    token_type: str = "bearer"
    is_admin: bool = False
    mfa_enabled: bool = False
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    message: Optional[str] = None

class TokenData(BaseModel):
    """Payload contenido dentro del Token JWT."""
    username: Optional[str] = None
    token_type: Optional[str] = "access"

class MFASetupResponse(BaseModel):
    """Respuesta para configuración de MFA (Código QR Base64 y secreto)."""
    secret_key: str
    qr_code_base64: str
    otpauth_url: str

class MFAVerifyRequest(BaseModel):
    """Payload para verificar o habilitar MFA con código de 6 dígitos."""
    code: str = Field(..., min_length=6, max_length=6, description="Código TOTP de 6 dígitos")

class MFALoginRequest(BaseModel):
    """Payload para completar login con MFA en 2do paso."""
    mfa_token: str = Field(..., description="Token de pre-autenticación devuelto en el primer paso")
    code: str = Field(..., min_length=6, max_length=6, description="Código TOTP de 6 dígitos de la app Authenticator")
