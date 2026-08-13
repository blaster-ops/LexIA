"""
Router de Glosario Jurídico (app/routers/glossary.py).
Endpoints para enriquecimiento, registro, consulta y eliminación de fichas jurídicas.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import glossary_repository
from app.services import get_current_user, glossary_service
from app.schemas import TerminoSchema, TerminoResponse

router = APIRouter(tags=["Glosario Jurídico"])

@router.post("/agregar_termino/", response_model=TerminoResponse, summary="Agregar y enriquecer un término jurídico")
async def agregar_termino(
    termino: TerminoSchema,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> TerminoResponse:
    """
    Enriquece el término jurídico mediante el modelo Ollama (gemma:7b)
    y lo guarda de forma persistente en MySQL asociado al usuario actual.
    """
    palabra_normalizada = termino.palabra.strip()
    materia_normalizada = termino.materia.strip()
    ficha_existente = glossary_repository.get_by_palabra_materia_and_propietario(
        db, palabra_normalizada, materia_normalizada, current_user
    )
    if ficha_existente and glossary_service.es_ficha_valida(
        ficha_existente.definicion_tecnica,
        ficha_existente.explicacion_sencilla,
        ficha_existente.mnemotecnia,
    ):
        respuesta = TerminoResponse.model_validate(ficha_existente)
        respuesta.existente = True
        return respuesta

    termino.palabra = palabra_normalizada
    termino.materia = materia_normalizada
    termino_enriquecido = await glossary_service.generar_enriquecimiento(termino)

    if ficha_existente:
        ficha = glossary_repository.update_content(
            db,
            ficha=ficha_existente,
            definicion_tecnica=termino_enriquecido.definicion_tecnica,
            explicacion_sencilla=termino_enriquecido.explicacion_sencilla,
            mnemotecnia=termino_enriquecido.mnemotecnia,
            materia=termino_enriquecido.materia,
        )
    else:
        ficha = glossary_repository.create(
            db,
            palabra=termino_enriquecido.palabra,
            definicion_tecnica=termino_enriquecido.definicion_tecnica,
            explicacion_sencilla=termino_enriquecido.explicacion_sencilla,
            mnemotecnia=termino_enriquecido.mnemotecnia,
            materia=termino_enriquecido.materia,
            propietario=current_user
        )

    return TerminoResponse.model_validate(ficha)

@router.get("/listar_terminos/", response_model=List[TerminoResponse], summary="Listar términos del usuario")
def listar_terminos(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> List[TerminoResponse]:
    """Retorna todas las fichas de glosario creadas por el usuario autenticado."""
    fichas = glossary_repository.list_by_propietario(db, current_user)
    return [TerminoResponse.model_validate(f) for f in fichas]

@router.get("/buscar_terminos/", response_model=List[TerminoResponse], summary="Buscar fichas por término")
def buscar_terminos(
    termino: str = Query(default="", max_length=255),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> List[TerminoResponse]:
    """Busca fichas del usuario mediante coincidencia parcial y sin distinguir mayúsculas."""
    fichas = glossary_repository.search_by_propietario(db, current_user, termino)
    return [TerminoResponse.model_validate(f) for f in fichas]

@router.delete("/borrar_termino_id/{ficha_id}", response_model=dict, summary="Eliminar una ficha por ID")
def borrar_termino_id(
    ficha_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> dict:
    """Elimina exactamente una ficha del usuario, incluso si existen términos homónimos."""
    ficha = glossary_repository.get_by_id_and_propietario(db, ficha_id, current_user)
    if not ficha:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ficha no encontrada.")
    palabra = ficha.palabra
    materia = ficha.materia
    glossary_repository.delete(db, ficha)
    return {"mensaje": f"Ficha '{palabra}' ({materia}) eliminada correctamente."}

@router.delete("/borrar_historial/", response_model=dict, summary="Vaciar todo el glosario del usuario")
def borrar_historial(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Elimina todas las fichas del glosario pertenecientes al usuario actual."""
    filas = glossary_repository.delete_all_by_propietario(db, current_user)
    return {"mensaje": f"Se eliminaron {filas} término(s) del historial."}

@router.delete("/borrar_termino/{palabra}", response_model=dict, summary="Eliminar un término del glosario")
def borrar_termino(
    palabra: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
) -> dict:
    """Elimina un término específico validando la propiedad de la ficha."""
    ficha = glossary_repository.get_by_palabra_and_propietario(db, palabra, current_user)
    if not ficha:
        # Verificar si pertenece a otro usuario
        otra = glossary_repository.get_by_palabra_any(db, palabra)
        if otra:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes autorización para eliminar una ficha perteneciente a otro usuario."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Término '{palabra}' no encontrado en tu glosario."
        )

    glossary_repository.delete(db, ficha)
    return {"mensaje": f"Término '{palabra}' eliminado correctamente."}
