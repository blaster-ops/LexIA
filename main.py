from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import pymongo
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

@app.get("/")
async def servir_inicio():
    return FileResponse("static/index.html")

# Conexión a MongoDB Atlas
client = pymongo.MongoClient("mongodb+srv://2eigth:1022445511Aa.@cluster0.o8vaxuo.mongodb.net/?appName=Cluster0")
db = client['lexia_db']
coleccion_glosario = db['fichas']

# Inicializar gestor de glosario
gestor_glosario = GestorGlosario()

@app.post("/agregar_termino/", response_model=Termino)
async def agregar_termino(termino: Termino):
    """
    Agrega un nuevo término al glosario.
    Genera automáticamente explicaciones sencillas y guarda en MongoDB.
    """
    gestor_glosario.generar_enriquecimiento(termino)
    coleccion_glosario.insert_one(termino.model_dump())
    return termino

@app.get("/listar_terminos/", response_model=List[Termino])
async def listar_terminos():
    """
    Devuelve todos los términos del glosario desde MongoDB.
    """
    fichas = list(coleccion_glosario.find({}, {'_id': 0}))
    return fichas

@app.delete("/borrar_historial/")
async def borrar_historial():
    """
    Elimina todo el historial de términos generados en MongoDB.
    """
    coleccion_glosario.delete_many({})
    return {"mensaje": "Historial eliminado correctamente"}

@app.delete("/borrar_termino/{palabra}")
async def borrar_termino(palabra: str):
    """
    Elimina un término específico del glosario.
    """
    resultado = coleccion_glosario.delete_one({'palabra': palabra})
    if resultado.deleted_count > 0:
        return {"mensaje": f"Término '{palabra}' eliminado correctamente."}
    else:
        raise HTTPException(status_code=404, detail="Término no encontrado.")

@app.post("/buscar_en_pdf/")
async def buscar_en_pdf(file: Optional[UploadFile] = File(None), keyword: Optional[str] = Form(None), filename_filter: Optional[str] = Form(None)):
    """
    Ruta corregida: Si hay una palabra clave, busca directamente en ChromaDB
    sin reprocesar el PDF. Si no la hay y hay archivo, ingesta el documento.
    """
    # Importaciones necesarias de Langchain
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    
    try:
        # Comportamiento 1: Búsqueda en la base de vectores (Lupa Legal)
        if keyword:
            print(f"DEBUG: Iniciando búsqueda rápida para '{keyword}' en ChromaDB... (Consumo estimado: 1 ticket)")
            # 1. Solo inicializar conexión a base de datos existente
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                task_type="retrieval_document"
            )
            vectorstore = Chroma(
                persist_directory="./chroma_db", 
                embedding_function=embeddings
            )
            
            # 2. Ejecutar similarity search directamente
            if filename_filter and str(filename_filter).strip() and str(filename_filter).lower() not in ["none", "null", "undefined"]:
                resultados = vectorstore.similarity_search(keyword, k=5, filter={'source': filename_filter})
            else:
                resultados = vectorstore.similarity_search(keyword, k=5)
            
            # 3. NO cargar, cortar ni procesar el PDF
            if resultados:
                fragmento = "\n\n".join([r.page_content for r in resultados])
                
                return {
                    "keyword": keyword,
                    "encontrado": True,
                    "fragmento": fragmento,
                    "documentos_extraidos": len(resultados),
                    "busqueda_realizada": True
                }
            else:
                return {
                    "keyword": keyword,
                    "encontrado": False,
                    "fragmento": "No se encontraron similitudes en la base de datos.",
                    "busqueda_realizada": True
                }

        # Comportamiento 2: Subida/Ingesta inicial de archivo PDF
        elif file and file.filename.lower().endswith('.pdf'):
            temp_filename = f"temp_{file.filename}"
            with open(temp_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Procesar y guardar lote en ChromaDB
            procesar_pdf(temp_filename)
            
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            return {
                "archivo": file.filename,
                "mensaje": "Archivo subido y procesado correctamente en ChromaDB.",
                "busqueda_realizada": False
            }
            
        else:
            raise HTTPException(status_code=400, detail="Debes enviar una palabra clave a buscar o un archivo PDF.")
            
    except Exception as e:
        import traceback
        print("🔥 ERROR DETALLADO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en la operación: {str(e)}")

@app.post("/preguntar_tutor/")
async def preguntar_tutor(pregunta: str, filename_filter: Optional[str] = None):
    """
    Responde preguntas usando el contexto de los PDFs subidos (RAG).
    Usa la nueva lógica centralizada en ingesta_pdf con Gemini 2.5 Flash.
    """
    if not pregunta or not pregunta.strip():
        raise HTTPException(status_code=400, detail="Error: La pregunta no puede estar vacía.")

    try:
        respuesta = preguntar_al_tutor(pregunta, filename_filter)
        return {"respuesta": respuesta}
        
    except Exception as e:
        # Detectar errores relacionados con falta de contexto/DB
        mensaje_error = str(e).lower()
        if "chroma" in mensaje_error or "directory" in mensaje_error or "collection" in mensaje_error or "no se encontró" in mensaje_error:
             raise HTTPException(status_code=400, detail="Error: Primero debes cargar un documento.")
        
        raise HTTPException(status_code=500, detail=f"Error en tutor IA: {str(e)}")

@app.get("/listar_archivos/")
async def listar_archivos():
    """
    Devuelve una lista de los nombres de archivo únicos guardados en ChromaDB.
    """
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        
        # Obtener todos los documentos y extraer fuentes únicas
        collection = vectorstore.get()
        metadatas = collection.get("metadatas", [])
        
        archivos_unicos = set()
        for meta in metadatas:
            if meta and "source" in meta:
                archivos_unicos.add(meta["source"])
                
        return {"archivos": list(archivos_unicos)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar archivos: {str(e)}")

@app.delete("/borrar_archivo/{filename}")
async def borrar_archivo(filename: str):
    """
    Elimina de ChromaDB todos los documentos cuya metadata 'source' coincida con 'filename'.
    """
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        
        # Primero buscar IDs de los chunks a borrar
        collection = vectorstore.get(where={"source": filename})
        ids_to_delete = collection.get("ids", [])
        
        if not ids_to_delete:
            return {"mensaje": f"No se encontró el archivo '{filename}' en la base de datos.", "eliminado": False}
        
        vectorstore.delete(ids=ids_to_delete)
        return {"mensaje": f"Se eliminó el archivo '{filename}' ({len(ids_to_delete)} fragmentos).", "eliminado": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al borrar archivo: {str(e)}")
