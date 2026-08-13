"""
Router para operaciones RAG y PDF (app/routers/rag.py).
Endpoints para la ingesta de documentos, búsqueda literal, tutoría IA y administración de ChromaDB.
"""
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.services import get_current_user, rag_service
from app.schemas import BusquedaPDFResponse, PreguntaTutorRequest, PreguntaTutorResponse, ListaArchivosResponse
from app.config import DATA_DIR, settings

router = APIRouter(tags=["RAG y Documentos PDF"])

@router.post("/buscar_en_pdf/", response_model=BusquedaPDFResponse, summary="Buscar palabra clave o ingestar PDF")
async def buscar_en_pdf(
    file: Optional[UploadFile] = File(None),
    keyword: Optional[str] = Form(None),
    filename_filter: Optional[str] = Form(None),
    current_user: str = Depends(get_current_user)
) -> BusquedaPDFResponse:
    """
    Si se envía una palabra clave (`keyword`), realiza búsqueda léxica literal en los PDFs subidos.
    Si se sube un nuevo archivo PDF (`file`), lo guarda e ingesta en ChromaDB.
    """
    safe_user = os.path.basename(current_user.lower())
    user_uploads_dir = os.path.join(DATA_DIR, safe_user, "uploads")

    # Caso 1: Búsqueda literal
    if keyword and keyword.strip():
        fragmento = await run_in_threadpool(rag_service.buscar_literal, safe_user, keyword.strip(), filename_filter)
        if fragmento:
            num_docs = len(fragmento.split("<br><br>"))
            return BusquedaPDFResponse(
                keyword=keyword.strip(),
                encontrado=True,
                fragmento=fragmento,
                documentos_extraidos=num_docs,
                busqueda_realizada=True
            )
        return BusquedaPDFResponse(
            keyword=keyword.strip(),
            encontrado=False,
            fragmento="No se encontró la palabra clave de forma literal en los documentos.",
            busqueda_realizada=True
        )

    # Caso 2: Ingesta de archivo PDF
    elif file and file.filename and file.filename.lower().endswith(".pdf"):
        # El MIME es una señal adicional; la firma real se valida al leer el contenido.
        if file.content_type not in ["application/pdf", "application/x-pdf", "application/octet-stream"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato inválido. Solo se admiten archivos PDF."
            )

        filename_seguro = os.path.basename(file.filename)
        if not filename_seguro or filename_seguro in {".", ".."}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo inválido.")

        os.makedirs(user_uploads_dir, exist_ok=True)
        ruta_destino = os.path.join(user_uploads_dir, filename_seguro)
        if os.path.exists(ruta_destino):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El archivo '{filename_seguro}' ya está indexado. Elimínalo antes de volver a subirlo."
            )

        ruta_temporal = f"{ruta_destino}.{uuid.uuid4().hex}.upload"
        limite_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        bytes_escritos = 0
        try:
            with open(ruta_temporal, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    if bytes_escritos == 0 and not chunk.startswith(b"%PDF-"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El contenido del archivo no corresponde a un PDF válido."
                        )
                    bytes_escritos += len(chunk)
                    if bytes_escritos > limite_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"El PDF supera el límite de {settings.MAX_UPLOAD_SIZE_MB} MB."
                        )
                    buffer.write(chunk)

            if bytes_escritos == 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El PDF está vacío.")

            os.replace(ruta_temporal, ruta_destino)
            num_chunks = await run_in_threadpool(rag_service.procesar_pdf_rag, ruta_destino, safe_user)
        except Exception:
            for ruta_incompleta in (ruta_temporal, ruta_destino):
                if os.path.exists(ruta_incompleta):
                    try:
                        os.remove(ruta_incompleta)
                    except OSError:
                        pass
            raise
        finally:
            await file.close()

        return BusquedaPDFResponse(
            archivo=filename_seguro,
            mensaje=f"Archivo '{filename_seguro}' procesado exitosamente en ChromaDB ({num_chunks} fragmentos indexados).",
            busqueda_realizada=False
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes proporcionar una palabra clave para buscar o adjuntar un archivo PDF válido."
        )

@router.post("/preguntar_tutor/", response_model=PreguntaTutorResponse, summary="Consultar al Consultor IA Legal (RAG)")
async def preguntar_tutor(
    payload: Optional[PreguntaTutorRequest] = None,
    pregunta: Optional[str] = Form(None),
    filename_filter: Optional[str] = Form(None),
    pregunta_query: Optional[str] = Query(None, alias="pregunta"),
    filename_filter_query: Optional[str] = Query(None, alias="filename_filter"),
    current_user: str = Depends(get_current_user)
) -> PreguntaTutorResponse:
    """
    Responde consultas jurídicas con contexto RAG utilizando el modelo local Ollama (gemma:7b).
    Soporta JSON Body, Form Data o Query Parameters para máxima compatibilidad con el cliente web.
    """
    texto_pregunta = None
    filtro_archivo = None

    if payload and payload.pregunta:
        texto_pregunta = payload.pregunta
        filtro_archivo = payload.filename_filter
    elif pregunta and pregunta.strip():
        texto_pregunta = pregunta
        filtro_archivo = filename_filter
    elif pregunta_query and pregunta_query.strip():
        texto_pregunta = pregunta_query
        filtro_archivo = filename_filter_query

    if not texto_pregunta or not texto_pregunta.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La pregunta enviada no puede estar vacia."
        )

    safe_user = os.path.basename(current_user.lower())
    respuesta = await rag_service.preguntar_al_tutor(texto_pregunta.strip(), safe_user, filtro_archivo)
    return PreguntaTutorResponse(respuesta=respuesta)

@router.get("/listar_archivos/", response_model=ListaArchivosResponse, summary="Listar archivos indexados del usuario")
async def listar_archivos(current_user: str = Depends(get_current_user)) -> ListaArchivosResponse:
    """Obtiene la lista de nombres de archivos cargados en la base de vectores ChromaDB."""
    safe_user = os.path.basename(current_user.lower())
    archivos = await run_in_threadpool(rag_service.listar_archivos_usuario, safe_user)
    return ListaArchivosResponse(archivos=archivos)

@router.delete("/borrar_archivo/{filename}", response_model=dict, summary="Eliminar archivo e índices vectoriales")
async def borrar_archivo(
    filename: str,
    current_user: str = Depends(get_current_user)
) -> dict:
    """Elimina el PDF físico y borra sus embeddings de ChromaDB."""
    safe_user = os.path.basename(current_user.lower())
    resultado = await run_in_threadpool(rag_service.borrar_archivo_usuario, safe_user, filename)
    return resultado
