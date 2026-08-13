"""
Router de Autenticación y MFA (app/routers/auth.py).
Gestiona el inicio de sesión en 2 pasos, expedición de tokens JWT y vinculación de MFA 100% offline.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import user_repository
from app.services import AuthService, get_current_user
from app.schemas import (
    Token,
    MFASetupResponse,
    MFAVerifyRequest,
    MFALoginRequest
)

router = APIRouter(tags=["Autenticación y MFA"])

@router.post("/login", response_model=Token, summary="Inicio de sesión de usuarios (Paso 1)")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> dict:
    """
    Autentica usuario con nombre y contraseña.
    Si el usuario tiene MFA activado, devuelve `mfa_required=True` y un `mfa_token` temporal.
    Si no tiene MFA activado, devuelve el Token JWT final.
    """
    username_lower = form_data.username.strip().lower()
    user = user_repository.get_by_username(db, username_lower)

    if not user or not AuthService.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar si el usuario tiene activado el doble factor (MFA)
    if user.mfa_enabled:
        preauth_token = AuthService.create_mfa_preauth_token(username=user.username)
        return {
            "mfa_required": True,
            "mfa_token": preauth_token,
            "message": "Se requiere ingresar el código TOTP de 6 dígitos de la aplicación Authenticator."
        }

    access_token = AuthService.create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_admin": user.is_admin,
        "mfa_enabled": user.mfa_enabled,
        "mfa_required": False
    }

@router.post("/login/mfa", response_model=Token, summary="Completar inicio de sesión con MFA (Paso 2)")
def login_mfa(
    payload: MFALoginRequest,
    db: Session = Depends(get_db)
) -> dict:
    """
    Valida el código TOTP de 6 dígitos con el token temporal de pre-autenticación y emite el Token JWT final.
    """
    decoded = AuthService.decode_access_token(payload.mfa_token)
    if decoded.get("type") != "mfa_preauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token MFA inválido o expirado. Por favor inicie sesión de nuevo."
        )

    username = decoded.get("sub")
    user = user_repository.get_by_username(db, username)
    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario no tiene configurado MFA o la cuenta no existe."
        )

    # Verificar matemáticamente el código de 6 dígitos localmente
    if not AuthService.verify_totp_code(user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de verificación TOTP incorrecto o expirado."
        )

    access_token = AuthService.create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_admin": user.is_admin,
        "mfa_enabled": True,
        "mfa_required": False
    }

@router.get("/me", summary="Obtener información del usuario autenticado")
def get_me(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Retorna los datos del usuario actual incluyendo su rol e historial de MFA."""
    user = user_repository.get_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {
        "username": user.username,
        "is_admin": user.is_admin,
        "mfa_enabled": user.mfa_enabled
    }

@router.post("/mfa/setup", response_model=MFASetupResponse, summary="Generar código QR para vincular Authenticator")
def mfa_setup(
    reset: bool = Query(False, description="Fuerza la generación de una nueva clave si es True"),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """
    Genera o recupera el secreto TOTP y su código QR en imagen Base64 para escanear con Google Authenticator.
    Reutiliza la clave si ya fue generada para evitar desincronización, a menos que reset=True.
    """
    user = user_repository.get_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # Si el usuario ya tiene un secreto TOTP asignado y no se solicita reseteo, reutilizarlo
    if user.mfa_secret and not reset:
        secret = user.mfa_secret
    else:
        secret = AuthService.generate_totp_secret()
        user_repository.set_mfa_secret(db, user, secret)

    totp_uri = AuthService.generate_totp_uri(user.username, secret)
    qr_base64 = AuthService.generate_qr_code_base64(totp_uri)

    return {
        "secret_key": secret,
        "qr_code_base64": qr_base64,
        "otpauth_url": totp_uri
    }

@router.post("/mfa/enable", response_model=dict, summary="Habilitar MFA tras confirmar código")
def mfa_enable(
    payload: MFAVerifyRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """
    Verifica el primer código de 6 dígitos generado por la app y activa oficialmente MFA para la cuenta.
    """
    user = user_repository.get_by_username(db, current_user)
    if not user or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero debes solicitar la configuración de MFA con /mfa/setup."
        )

    if not AuthService.verify_totp_code(user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código TOTP incorrecto. Asegúrate de ingresar el código actual de tu aplicación Authenticator."
        )

    user_repository.enable_mfa(db, user, user.mfa_secret)
    return {"mensaje": "Autenticación de Doble Factor (MFA) activada exitosamente."}

@router.post("/mfa/disable", response_model=dict, summary="Desactivar MFA")
def mfa_disable(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Desactiva la autenticación de doble factor para el usuario autenticado."""
    user = user_repository.get_by_username(db, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    user_repository.disable_mfa(db, user)
    return {"mensaje": "Autenticación de Doble Factor (MFA) desactivada correctamente."}
