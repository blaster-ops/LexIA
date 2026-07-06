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
# DEBE ejecutarse antes que cualquier otra lógica de procesos.
import multiprocessing
multiprocessing.freeze_support()

# ── Forzar UTF-8 en stdout/stderr para evitar crash 'charmap' en Windows sin consola ──
import sys
import io
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def print(*args, **kwargs):
    import builtins
    safe_args = []
    for arg in args:
        if isinstance(arg, str):
            safe_args.append(arg.encode('ascii', 'backslashreplace').decode('ascii'))
        else:
            safe_args.append(arg)
    try:
        if sys.stdout is not None:
            builtins.print(*safe_args, **kwargs)
    except Exception:
        pass

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import shutil
import os

load_dotenv()
import secrets
import threading
import time
import uvicorn
import multiprocessing
import webview
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from glosario import GestorGlosario, Termino
from ingesta_pdf import procesar_pdf, buscar_literal_en_pdf, buscar_contexto, preguntar_al_tutor

# --- RESOLUCIÓN DE RUTAS (funciona en .py y en .exe compilado) ---
import sys
if getattr(sys, 'frozen', False):
    # Ejecutando como .exe: archivos estáticos en carpeta temporal (solo lectura)
    BASE_DIR = sys._MEIPASS
    # Datos persistentes (DB, uploads) junto al .exe (escritura)
    APP_DIR  = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR  = BASE_DIR

STATIC_DIR  = os.path.join(BASE_DIR, "static")
DATA_DIR    = os.path.join(APP_DIR,  "data", "users")
DB_PATH     = os.path.join(APP_DIR,  "usuarios.db")

# --- CONFIGURACIÓN ---
app = FastAPI(title="LexIA: Asistente Jurídico Inteligente")

# --- BASE DE DATOS Y AUTENTICACIÓN ---
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class FichaGlosario(Base):
    __tablename__ = "fichas_glosario"
    id = Column(Integer, primary_key=True, index=True)
    palabra = Column(String, index=True)
    definicion_tecnica = Column(String)
    explicacion_sencilla = Column(String)
    mnemotecnia = Column(String)
    materia = Column(String)
    propietario = Column(String, index=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# C-2: Llave JWT leída desde variable de entorno para evitar hardcoding
SECRET_KEY = os.environ.get("LEXIA_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    return username

class UsuarioCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@app.on_event("startup")
def crear_admin_inicial():
    db = SessionLocal()
    try:
        if db.query(Usuario).count() == 0:
            # C-1: Contraseña leída desde variable de entorno para evitar hardcoding
            password_segura = os.getenv("ADMIN_PASSWORD", "1022445511")
            hashed_password = bcrypt.hashpw(password_segura.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            nuevo_admin = Usuario(username="2eigth", password_hash=hashed_password)
            db.add(nuevo_admin)
            db.commit()
            print("Base de datos inicializada: Usuario 2eigth listo")
    except Exception as e:
        print(f"Error al inicializar admin: {e}")
    finally:
        db.close()

@app.post("/login", response_model=Token)
def login_usuario(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    username_lower = form_data.username.lower()
    db_user = db.query(Usuario).filter(Usuario.username == username_lower).first()
    if not db_user or not bcrypt.checkpw(form_data.password.encode('utf-8'), db_user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode = {"sub": db_user.username, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": encoded_jwt, "token_type": "bearer"}

@app.post("/admin/crear_usuario", response_model=dict)
def crear_usuario_admin(user: UsuarioCreate, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    if current_user != "2eigth":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador.")
    username_lower = user.username.lower()
    db_user = db.query(Usuario).filter(Usuario.username == username_lower).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    nuevo_usuario = Usuario(username=username_lower, password_hash=hashed_password)
    db.add(nuevo_usuario)
    db.commit()
    # Crear directorios
    os.makedirs(os.path.join(DATA_DIR, username_lower, "uploads"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, username_lower, "chroma_db"), exist_ok=True)
    return {"mensaje": f"Usuario '{username_lower}' creado exitosamente."}

@app.get("/admin/usuarios", response_model=List[str])
def listar_usuarios_admin(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    if current_user != "2eigth":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador.")
    usuarios = db.query(Usuario).all()
    return [u.username for u in usuarios]

@app.delete("/admin/borrar_usuario/{username}", response_model=dict)
def borrar_usuario_admin(username: str, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    if current_user != "2eigth":
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador.")
    if username == "2eigth":
        raise HTTPException(status_code=400, detail="No se puede eliminar al administrador principal.")
        
    db_user = db.query(Usuario).filter(Usuario.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    db.delete(db_user)
    db.commit()
    
    # Eliminar directorio físico
    user_dir = os.path.join(DATA_DIR, username)
    if os.path.exists(user_dir):
        try:
            shutil.rmtree(user_dir)
        except Exception as e:
            print(f"Error al eliminar directorio físico {user_dir}: {e}")
            
    return {"mensaje": f"Usuario '{username}' y sus datos han sido eliminados correctamente."}

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def servir_inicio():
    return FileResponse(os.path.join(STATIC_DIR, "index_despacho.html"))

# Inicializar gestor de glosario
gestor_glosario = GestorGlosario()

from starlette.concurrency import run_in_threadpool

@app.post("/agregar_termino/", response_model=Termino)
async def agregar_termino(termino: Termino, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """
    Agrega un nuevo término al glosario.
    Genera automáticamente explicaciones sencillas y guarda en SQLite.
    """
    print("DEBUG: Iniciando enriquecimiento de glosario...")
    await gestor_glosario.generar_enriquecimiento(termino)
    
    nueva_ficha = FichaGlosario(
        palabra=termino.palabra,
        definicion_tecnica=termino.definicion_tecnica,
        explicacion_sencilla=termino.explicacion_sencilla,
        mnemotecnia=termino.mnemotecnia,
        materia=termino.materia,
        propietario=current_user
    )
    db.add(nueva_ficha)
    db.commit()
    print("DEBUG: Termino guardado en SQLite de forma aislada.")
    
    return termino

@app.get("/listar_terminos/", response_model=List[Termino])
async def listar_terminos(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """
    Devuelve todos los términos del glosario para el tenant actual.
    """
    print("DEBUG: Leyendo terminos aislados desde SQLite...")
    fichas = db.query(FichaGlosario).filter(FichaGlosario.propietario == current_user).all()
    return [
        Termino(
            palabra=f.palabra,
            definicion_tecnica=f.definicion_tecnica,
            explicacion_sencilla=f.explicacion_sencilla,
            mnemotecnia=f.mnemotecnia,
            materia=f.materia
        ) for f in fichas
    ]

@app.delete("/borrar_historial/")
async def borrar_historial(db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """
    Elimina todo el historial de términos generados para el tenant actual.
    """
    print("DEBUG: Vaciando historial del usuario en SQLite...")
    db.query(FichaGlosario).filter(FichaGlosario.propietario == current_user).delete()
    db.commit()
    return {"mensaje": "Historial eliminado correctamente"}

@app.delete("/borrar_termino/{palabra}")
async def borrar_termino(palabra: str, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)):
    """
    Elimina un término específico del glosario para el tenant actual.
    Valida la propiedad antes de borrar.
    """
    print(f"DEBUG: Intentando eliminar '{palabra}' de SQLite...")
    ficha = db.query(FichaGlosario).filter(FichaGlosario.palabra == palabra, FichaGlosario.propietario == current_user).first()
    
    if not ficha:
        # Verificar si la ficha existe pero pertenece a otro usuario
        otra_ficha = db.query(FichaGlosario).filter(FichaGlosario.palabra == palabra).first()
        if otra_ficha:
            raise HTTPException(status_code=403, detail="No tienes permiso para borrar esta ficha porque le pertenece a otro usuario.")
        raise HTTPException(status_code=404, detail="Término no encontrado.")
        
    db.delete(ficha)
    db.commit()
    return {"mensaje": f"Término '{palabra}' eliminado correctamente."}

@app.post("/buscar_en_pdf/")
async def buscar_en_pdf(file: Optional[UploadFile] = File(None), keyword: Optional[str] = Form(None), filename_filter: Optional[str] = Form(None), username: str = Depends(get_current_user)):
    """
    Ruta corregida: Si hay una palabra clave, busca directamente en ChromaDB
    sin reprocesar el PDF. Si no la hay y hay archivo, ingesta el documento.
    """
    try:
        user_uploads_dir = os.path.join(DATA_DIR, username, "uploads")
        # Comportamiento 1: Búsqueda Literal (Lupa Legal)
        if keyword:
            print(f"DEBUG: Iniciando busqueda literal para '{keyword}'...")
            
            def buscar_literal():
                archivos_a_buscar = []
                if filename_filter and str(filename_filter).strip() and str(filename_filter).lower() not in ["none", "null", "undefined"]:
                    # C-2: Sanitizar filename_filter para prevenir Path Traversal (ej: ../../usuarios.db)
                    filename_seguro = os.path.basename(filename_filter)
                    ruta = os.path.join(user_uploads_dir, filename_seguro)
                    if os.path.exists(ruta):
                        archivos_a_buscar.append(ruta)
                else:
                    # Buscar en todos los uploads si no hay filtro
                    if os.path.exists(user_uploads_dir):
                        for f in os.listdir(user_uploads_dir):
                            if f.lower().endswith(".pdf"):
                                archivos_a_buscar.append(os.path.join(user_uploads_dir, f))
                                
                resultados_totales = []
                for ruta in archivos_a_buscar:
                    res = buscar_literal_en_pdf(ruta, keyword)
                    if res:
                        if len(archivos_a_buscar) > 1:
                            resultados_totales.append(f"<b>[{os.path.basename(ruta)}]</b><br>{res}")
                        else:
                            resultados_totales.append(res)
                            
                return "<br><br>".join(resultados_totales)
                
            fragmento_final = await run_in_threadpool(buscar_literal)
            
            if fragmento_final:
                return {
                    "keyword": keyword,
                    "encontrado": True,
                    "fragmento": fragmento_final,
                    "documentos_extraidos": len(fragmento_final.split("<br><br>")),
                    "busqueda_realizada": True
                }
            else:
                return {
                    "keyword": keyword,
                    "encontrado": False,
                    "fragmento": "No se encontró la palabra clave de forma literal en el documento.",
                    "busqueda_realizada": True
                }

        # Comportamiento 2: Subida/Ingesta inicial de archivo PDF
        elif file and file.filename.lower().endswith('.pdf'):
            # C-3: Validar MIME Type real para bloquear malware disfrazado como PDF
            if file.content_type != "application/pdf":
                raise HTTPException(status_code=400, detail="Archivo inválido. Posible riesgo de seguridad.")
            os.makedirs(user_uploads_dir, exist_ok=True)
            saved_filename = os.path.join(user_uploads_dir, file.filename)
            with open(saved_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Procesar y guardar lote en ChromaDB
            print(f"DEBUG: Iniciando procesamiento e ingesta de '{file.filename}' en ChromaDB para {username}...")
            await run_in_threadpool(procesar_pdf, saved_filename, username)
            print("DEBUG: Ingesta completada.")
                
            return {
                "archivo": file.filename,
                "mensaje": "Archivo subido y procesado correctamente en ChromaDB.",
                "busqueda_realizada": False
            }
            
        else:
            raise HTTPException(status_code=400, detail="Debes enviar una palabra clave a buscar o un archivo PDF.")
            
    except Exception as e:
        import traceback
        print("ERROR DETALLADO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en la operación: {str(e)}")

@app.post("/preguntar_tutor/")
async def preguntar_tutor(pregunta: str, filename_filter: Optional[str] = None, username: str = Depends(get_current_user)):
    """
    Responde preguntas usando el contexto de los PDFs subidos (RAG).
    Usa la lógica centralizada en ingesta_pdf con Ollama local.
    """
    if not pregunta or not pregunta.strip():
        raise HTTPException(status_code=400, detail="Error: La pregunta no puede estar vacía.")

    try:
        print(f"DEBUG: Iniciando solicitud al tutor IA para el usuario {username}...")
        respuesta = await preguntar_al_tutor(pregunta, username, filename_filter)
        print("DEBUG: Respuesta final enviada al cliente.")
        return {"respuesta": respuesta}
        
    except Exception as e:
        # Detectar errores relacionados con falta de contexto/DB
        mensaje_error = str(e).lower()
        if "chroma" in mensaje_error or "directory" in mensaje_error or "collection" in mensaje_error or "no se encontró" in mensaje_error:
             raise HTTPException(status_code=400, detail="Error: Primero debes cargar un documento.")
        
        raise HTTPException(status_code=500, detail=f"Error en tutor IA: {str(e)}")

@app.get("/listar_archivos/")
async def listar_archivos(username: str = Depends(get_current_user)):
    """
    Devuelve una lista de los nombres de archivo únicos guardados en ChromaDB.
    """
    try:
        user_chroma_dir = os.path.join(DATA_DIR, username, "chroma_db")
        def procesar_listado():
            print(f"DEBUG: Listando archivos de ChromaDB para {username}...")
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
            vectorstore = Chroma(persist_directory=user_chroma_dir, embedding_function=embeddings)
            
            # Obtener todos los documentos y extraer fuentes únicas
            collection = vectorstore.get()
            return collection.get("metadatas", [])
            
        metadatas = await run_in_threadpool(procesar_listado)
        
        archivos_unicos = set()
        for meta in metadatas:
            if meta and "source" in meta:
                archivos_unicos.add(meta["source"])
                
        print("DEBUG: Listado de archivos completado.")
        return {"archivos": list(archivos_unicos)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")

@app.delete("/borrar_archivo/{filename}")
async def borrar_archivo(filename: str, username: str = Depends(get_current_user)):
    """
    Elimina de ChromaDB todos los documentos cuya metadata 'source' coincida con 'filename',
    y también elimina el archivo físico de la carpeta uploads.
    """
    try:
        user_uploads_dir = os.path.join(DATA_DIR, username, "uploads")
        user_chroma_dir  = os.path.join(DATA_DIR, username, "chroma_db")
        
        # C-4: Sanitizar filename para prevenir Path Traversal (ej: ../../usuarios.db)
        filename_safe = os.path.basename(filename)
        ruta_archivo = os.path.join(user_uploads_dir, filename_safe)
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
            print(f"DEBUG: Archivo fisico '{filename_safe}' eliminado de {user_uploads_dir}.")

        def procesar_borrado():
            print(f"DEBUG: Buscando archivo '{filename_safe}' en ChromaDB para borrar...")
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
            vectorstore = Chroma(persist_directory=user_chroma_dir, embedding_function=embeddings)
            
            # Primero buscar IDs de los chunks a borrar
            collection = vectorstore.get(where={"source": filename_safe})
            ids_to_delete = collection.get("ids", [])
            
            if not ids_to_delete:
                return {"mensaje": f"No se encontró el archivo '{filename_safe}' en la base de datos, pero el archivo físico fue removido si existía.", "eliminado": False}
            
            vectorstore.delete(ids=ids_to_delete)
            return {"mensaje": f"Se eliminó el archivo '{filename_safe}' ({len(ids_to_delete)} fragmentos) y el archivo físico.", "eliminado": True}
            
        resultado = await run_in_threadpool(procesar_borrado)
        print(f"DEBUG: Archivo '{filename}' borrado de ChromaDB.")
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al borrar archivo: {str(e)}")


def run_fastapi():
    # Objeto app directo + workers=1 para evitar subprocesos en entorno frozen
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", reload=False, workers=1)

if __name__ == "__main__":
    multiprocessing.freeze_support()  # ← PRIMERA línea absoluta, crítico en Windows

    # 1. Arrancar el servidor en un hilo secundario (para que no bloquee)
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()

    # 2. Darle 1.5 segundos al servidor para que despierte bien
    time.sleep(1.5)

    # 3. Lanzar la ventana nativa en el hilo principal
    ventana = webview.create_window(
        title="LexIA - Emerald Systems",
        url="http://127.0.0.1:8000",
        width=1280,
        height=800
    )
    webview.start()

