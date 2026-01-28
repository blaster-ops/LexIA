from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
import shutil
import os
from typing import List, Optional
import secrets
import base64
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import google.generativeai as genai

# --- BASE DE DATOS DE USUARIOS ---
USERS_DB = {
    "2eigth": "1022445511Aa",    # Usuario Administrador
    "Miri": "200730"       # Usuario Invitado
}

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return Response("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Basic"})
        
        try:
            scheme, credentials = auth_header.split()
            if scheme.lower() != 'basic':
                return Response("Invalid authentication scheme", status_code=401, headers={"WWW-Authenticate": "Basic"})
            
            decoded = base64.b64decode(credentials).decode("ascii")
            username, _, password = decoded.partition(":")
            
            if username in USERS_DB:
                # Verificar contraseña de forma segura
                is_correct = secrets.compare_digest(password, USERS_DB[username])
                if is_correct:
                    return await call_next(request)
            
            return Response("Invalid credentials", status_code=401, headers={"WWW-Authenticate": "Basic"})
            
        except Exception:
            return Response("Invalid authorization header", status_code=401, headers={"WWW-Authenticate": "Basic"})

# --- CONFIGURACIÓN ---
os.environ["GOOGLE_API_KEY"] = "AIzaSyChHxqXdmyB-jK2PSt-N1tPtYaoJFLp4pI"


from glosario import GestorGlosario, Termino
from ingesta_pdf import procesar_pdf, buscar_palabra, buscar_contexto, preguntar_al_tutor

# --- CONFIGURACIÓN ---


app = FastAPI(title="LexIA: Asistente Jurídico Inteligente")
app.add_middleware(SecurityMiddleware)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inicializar gestor de glosario
gestor_glosario = GestorGlosario()

@app.post("/agregar_termino/", response_model=Termino)
async def agregar_termino(termino: Termino):
    """
    Agrega un nuevo término al glosario.
    Ahora genera automáticamente explicaciones sencillas y mnemotecnias con IA.
    """
    gestor_glosario.guardar_termino(termino)
    return termino

@app.get("/terminos/", response_model=List[Termino])
async def listar_terminos():
    """
    Devuelve todos los términos del glosario.
    """
    return gestor_glosario.obtener_terminos()

@app.delete("/borrar_historial/")
async def borrar_historial():
    """
    Elimina todo el historial de términos generados.
    """
    gestor_glosario.limpiar_historial()
    return {"mensaje": "Historial eliminado correctamente"}

@app.post("/buscar_en_pdf/")
async def buscar_en_pdf(file: UploadFile = File(...), keyword: Optional[str] = None):
    """
    Sube un archivo PDF, extrae su texto, lo indexa para RAG.
    Si se proporciona una keyword, realiza una búsqueda simple (legacy).
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Error: Solo se permiten archivos PDF.")
    
    # Guardar archivo temporalmente
    temp_filename = f"temp_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Procesar PDF (Esto ahora también genera embeddings en ChromaDB)
        texto_extraido = procesar_pdf(temp_filename)
        
        # Si NO hay keyword, terminamos aquí
        if not keyword:
            return {
                "archivo": file.filename,
                "mensaje": "Archivo subido y procesado correctamente para RAG.",
                "busqueda_realizada": False
            }

        # Comportamiento legacy: Buscar palabra (Búsqueda simple)
        resultado = buscar_palabra(texto_extraido, keyword)
        
        return {
            "archivo": file.filename,
            "keyword": keyword,
            "encontrado": resultado is not None,
            "fragmento": resultado if resultado else "No se encontró la palabra clave.",
            "busqueda_realizada": True
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.post("/preguntar_tutor/")
async def preguntar_tutor(pregunta: str):
    """
    Responde preguntas usando el contexto de los PDFs subidos (RAG).
    Usa la nueva lógica centralizada en ingesta_pdf con Gemini 2.5 Flash.
    """
    if not pregunta or not pregunta.strip():
        raise HTTPException(status_code=400, detail="Error: La pregunta no puede estar vacía.")

    try:
        respuesta = preguntar_al_tutor(pregunta)
        return {"respuesta": respuesta}
        
    except Exception as e:
        # Detectar errores relacionados con falta de contexto/DB
        mensaje_error = str(e).lower()
        if "chroma" in mensaje_error or "directory" in mensaje_error or "collection" in mensaje_error or "no se encontró" in mensaje_error:
             raise HTTPException(status_code=400, detail="Error: Primero debes cargar un documento.")
        
        raise HTTPException(status_code=500, detail=f"Error en tutor IA: {str(e)}")
