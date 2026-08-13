"""
Servicio de Autenticación y Seguridad (app/services/auth_service.py).
Implementa hashing con passlib/bcrypt, Tokens JWT y Autenticación TOTP MFA 100% Offline.
"""
import io
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import pyotp
import qrcode
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import settings

# Configuración del contexto de hashing con passlib (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class AuthService:
    """Servicio encargado de la seguridad, hashing de contraseñas, JWT y TOTP MFA 100% offline."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifica una contraseña en texto plano contra su hash bcrypt."""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Genera un hash seguro utilizando el algoritmo bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crea un token JWT firmado con el tiempo de expiración configurado."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.LEXIA_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_mfa_preauth_token(username: str) -> str:
        """Crea un token de pre-autenticación de 10 minutos para verificar el 2do paso MFA."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=10)
        to_encode = {"sub": username, "exp": expire, "type": "mfa_preauth"}
        return jwt.encode(to_encode, settings.LEXIA_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """Decodifica y valida la firma y expiración de un token JWT."""
        try:
            payload = jwt.decode(token, settings.LEXIA_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de acceso ha expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acceso inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def generate_totp_secret() -> str:
        """Genera una clave secreta aleatoria en Base32 para TOTP RFC 6238 (100% offline)."""
        return pyotp.random_base32()

    @staticmethod
    def generate_totp_uri(username: str, secret: str) -> str:
        """Genera la URI estandarizada otpauth:// para escaneo en Google/Microsoft Authenticator."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name="LexIA Jurídico")

    @staticmethod
    def generate_qr_code_base64(totp_uri: str) -> str:
        """Genera la imagen del código QR en formato data URI (base64) para renderizar en el frontend sin internet."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=2,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def verify_totp_code(secret: str, code: str) -> bool:
        """
        Verifica un código TOTP de 6 dígitos mediante algoritmo matemático local (100% offline).
        Permite una ventana anterior y posterior para tolerar pequeños desfases de reloj.
        """
        if not secret or not code:
            return False
        clean_code = "".join(filter(str.isdigit, str(code)))
        if len(clean_code) != 6:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(clean_code, valid_window=1)

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Inyector de dependencia para FastAPI que extrae el usuario autenticado desde el token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de autenticación",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = AuthService.decode_access_token(token)
    if payload.get("type") == "mfa_preauth":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token incompleto. Se requiere completar la verificación MFA de 6 dígitos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise credentials_exception
    return username
