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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
import json
import uvicorn
import multiprocessing
from typing import List, Optional

from glosario import GestorGlosario, Termino
from ingesta_pdf import procesar_pdf, buscar_literal_en_pdf, buscar_contexto, preguntar_al_tutor

# --- CONFIGURACIÓN ---


app = FastAPI(title="LexIA: Asistente Jurídico Inteligente")

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def servir_inicio():
    return FileResponse("static/index.html")

# Almacenamiento local JSON
GLOSARIO_FILE = "base_datos_glosario.json"

def leer_glosario():
    if not os.path.exists(GLOSARIO_FILE):
        return []
    try:
        with open(GLOSARIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def guardar_glosario(datos):
    with open(GLOSARIO_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

# Inicializar gestor de glosario
gestor_glosario = GestorGlosario()

from starlette.concurrency import run_in_threadpool

@app.post("/agregar_termino/", response_model=Termino)
async def agregar_termino(termino: Termino):
    """
    Agrega un nuevo término al glosario.
    Genera automáticamente explicaciones sencillas y guarda en JSON local.
    """
    print("DEBUG: Iniciando enriquecimiento de glosario...")
    await gestor_glosario.generar_enriquecimiento(termino)
    
    print("DEBUG: Leyendo base_datos_glosario.json...")
    fichas = await run_in_threadpool(leer_glosario)
    fichas.append(termino.model_dump())
    
    print("DEBUG: Guardando en base_datos_glosario.json...")
    await run_in_threadpool(guardar_glosario, fichas)
    print("DEBUG: Término guardado en JSON local.")
    
    return termino

@app.get("/listar_terminos/", response_model=List[Termino])
async def listar_terminos():
    """
    Devuelve todos los términos del glosario desde archivo local.
    """
    print("DEBUG: Leyendo términos del JSON local...")
    return await run_in_threadpool(leer_glosario)

@app.delete("/borrar_historial/")
async def borrar_historial():
    """
    Elimina todo el historial de términos generados en archivo local.
    """
    print("DEBUG: Vaciando historial en JSON local...")
    await run_in_threadpool(guardar_glosario, [])
    return {"mensaje": "Historial eliminado correctamente"}

@app.delete("/borrar_termino/{palabra}")
async def borrar_termino(palabra: str):
    """
    Elimina un término específico del glosario del archivo local.
    """
    print(f"DEBUG: Eliminando '{palabra}' del JSON local...")
    fichas = await run_in_threadpool(leer_glosario)
    fichas_filtradas = [f for f in fichas if f.get('palabra') != palabra]
    
    if len(fichas) == len(fichas_filtradas):
        raise HTTPException(status_code=404, detail="Término no encontrado.")
        
    await run_in_threadpool(guardar_glosario, fichas_filtradas)
    return {"mensaje": f"Término '{palabra}' eliminado correctamente."}

@app.post("/buscar_en_pdf/")
async def buscar_en_pdf(file: Optional[UploadFile] = File(None), keyword: Optional[str] = Form(None), filename_filter: Optional[str] = Form(None)):
    """
    Ruta corregida: Si hay una palabra clave, busca directamente en ChromaDB
    sin reprocesar el PDF. Si no la hay y hay archivo, ingesta el documento.
    """
    # Importaciones necesarias de Langchain
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    
    try:
        # Comportamiento 1: Búsqueda Literal (Lupa Legal)
        if keyword:
            print(f"DEBUG: Iniciando búsqueda literal para '{keyword}'...")
            
            def buscar_literal():
                archivos_a_buscar = []
                if filename_filter and str(filename_filter).strip() and str(filename_filter).lower() not in ["none", "null", "undefined"]:
                    ruta = os.path.join("uploads", filename_filter)
                    if os.path.exists(ruta):
                        archivos_a_buscar.append(ruta)
                else:
                    # Buscar en todos los uploads si no hay filtro
                    if os.path.exists("uploads"):
                        for f in os.listdir("uploads"):
                            if f.lower().endswith(".pdf"):
                                archivos_a_buscar.append(os.path.join("uploads", f))
                                
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
            os.makedirs("uploads", exist_ok=True)
            saved_filename = os.path.join("uploads", file.filename)
            with open(saved_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Procesar y guardar lote en ChromaDB
            print(f"DEBUG: Iniciando procesamiento e ingesta de '{file.filename}' en ChromaDB...")
            await run_in_threadpool(procesar_pdf, saved_filename)
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
        print("🔥 ERROR DETALLADO:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en la operación: {str(e)}")

@app.post("/preguntar_tutor/")
async def preguntar_tutor(pregunta: str, filename_filter: Optional[str] = None):
    """
    Responde preguntas usando el contexto de los PDFs subidos (RAG).
    Usa la lógica centralizada en ingesta_pdf con Ollama local.
    """
    if not pregunta or not pregunta.strip():
        raise HTTPException(status_code=400, detail="Error: La pregunta no puede estar vacía.")

    try:
        print("DEBUG: Iniciando solicitud al tutor IA...")
        respuesta = await preguntar_al_tutor(pregunta, filename_filter)
        print("DEBUG: Respuesta final enviada al cliente.")
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
    from langchain_huggingface import HuggingFaceEmbeddings
    try:
        def procesar_listado():
            print("DEBUG: Listando archivos de ChromaDB...")
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
            vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            
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
async def borrar_archivo(filename: str):
    """
    Elimina de ChromaDB todos los documentos cuya metadata 'source' coincida con 'filename',
    y también elimina el archivo físico de la carpeta uploads.
    """
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    try:
        # Borrar el archivo físico si existe
        ruta_archivo = os.path.join("uploads", filename)
        if os.path.exists(ruta_archivo):
            os.remove(ruta_archivo)
            print(f"DEBUG: Archivo físico '{filename}' eliminado de uploads/.")

        def procesar_borrado():
            print(f"DEBUG: Buscando archivo '{filename}' en ChromaDB para borrar...")
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
            vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            
            # Primero buscar IDs de los chunks a borrar
            collection = vectorstore.get(where={"source": filename})
            ids_to_delete = collection.get("ids", [])
            
            if not ids_to_delete:
                return {"mensaje": f"No se encontró el archivo '{filename}' en la base de datos, pero el archivo físico fue removido si existía.", "eliminado": False}
            
            vectorstore.delete(ids=ids_to_delete)
            return {"mensaje": f"Se eliminó el archivo '{filename}' ({len(ids_to_delete)} fragmentos) y el archivo físico.", "eliminado": True}
            
        resultado = await run_in_threadpool(procesar_borrado)
        print(f"DEBUG: Archivo '{filename}' borrado de ChromaDB.")
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al borrar archivo: {str(e)}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    print("Iniciando LexIA Local Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

