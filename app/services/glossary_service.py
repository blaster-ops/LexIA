"""
Servicio de Enriquecimiento de Glosario con Ollama (app/services/glossary_service.py).
Genera definiciones, explicaciones sencillas y mnemotecnias mediante el modelo local Ollama.
"""
import json
import logging
import re
import httpx
from fastapi import HTTPException, status
from app.config import settings
from app.schemas.glossary import TerminoSchema
from app.exceptions import OllamaServiceError

logger = logging.getLogger("lexia.services.glossary")

class GlossaryService:
    """Servicio para enriquecimiento inteligente de términos jurídicos con Ollama."""

    CAMPOS_REQUERIDOS = (
        "definicion_tecnica",
        "explicacion_sencilla",
        "mnemotecnia",
    )
    TEXTOS_RESPALDO = {
        "concepto jurídico fundamental.",
        "recordar según el contexto de la materia.",
    }

    @classmethod
    def _extraer_json(cls, texto: str) -> dict:
        """Extrae un objeto JSON incluso si el modelo añade un bloque Markdown."""
        contenido = (texto or "").strip()
        if "```" in contenido:
            bloques = re.findall(r"```(?:json)?\s*([\s\S]*?)```", contenido, flags=re.IGNORECASE)
            if bloques:
                contenido = bloques[0].strip()

        inicio = contenido.find("{")
        fin = contenido.rfind("}")
        if inicio < 0 or fin <= inicio:
            raise ValueError("La respuesta no contiene un objeto JSON completo.")
        return json.loads(contenido[inicio:fin + 1])

    @classmethod
    def _validar_datos_ia(cls, datos: dict) -> dict:
        """Valida que la respuesta sea completa y no contenga textos genéricos de respaldo."""
        if not isinstance(datos, dict):
            raise ValueError("La respuesta estructurada no es un objeto.")

        minimos = {
            "definicion_tecnica": 80,
            "explicacion_sencilla": 60,
            "mnemotecnia": 12,
        }
        resultado = {}
        for campo in cls.CAMPOS_REQUERIDOS:
            valor = str(datos.get(campo, "")).strip()
            if len(valor) < minimos[campo]:
                raise ValueError(f"El campo '{campo}' es demasiado breve o está vacío.")
            if valor.lower() in cls.TEXTOS_RESPALDO or valor.lower().startswith("definición generada para"):
                raise ValueError(f"El campo '{campo}' contiene texto genérico de respaldo.")
            resultado[campo] = valor
        return resultado

    @classmethod
    def es_ficha_valida(cls, definicion: str, explicacion: str, mnemotecnia: str) -> bool:
        """Indica si una ficha almacenada cumple la calidad mínima actual."""
        try:
            cls._validar_datos_ia({
                "definicion_tecnica": definicion,
                "explicacion_sencilla": explicacion,
                "mnemotecnia": mnemotecnia,
            })
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    async def generar_enriquecimiento(termino: TerminoSchema) -> TerminoSchema:
        """
        Consulta al modelo Ollama (gemma:7b) para obtener definición técnica,
        explicación didáctica y regla mnemotécnica en formato JSON.
        Reforzado con frontera estricta de dominio jurídico.
        """
        prompt_base = f"""
[REGLA ABSOLUTA DE ROL]
Eres LexIA, un especialista en investigación jurídica para despachos profesionales. Redacta en español claro, preciso y verificable.
Si la palabra '{termino.palabra}' no guarda relación alguna con el Derecho o las ciencias jurídicas, indica amablemente que el término no pertenece al ámbito legal.

Para el término jurídico '{termino.palabra}' correspondiente a la materia '{termino.materia}':
1. Genera una definición técnica formal y rigurosa de al menos 80 caracteres.
2. Explica en lenguaje sencillo su aplicación práctica y relevancia profesional, con al menos 60 caracteres.
3. Crea una mnemotecnia breve pero útil.
4. Si mencionas legislación, jurisprudencia, artículos o autoridades, no inventes referencias. Si la jurisdicción no está especificada, aclara que el fundamento concreto depende del país.
5. No uses frases vacías como "concepto jurídico fundamental" o "recordar según el contexto".
6. Antes de responder, revisa silenciosamente precisión conceptual, concordancia, ortografía y naturalidad del español. No uses expresiones ambiguas como "situaciones emergentes" cuando corresponda "situaciones de emergencia".
7. La definición debe explicar qué es el concepto, cuándo opera y qué efecto jurídico produce; evita limitarte a repetir las palabras del término.
8. La mnemotecnia debe ayudar a recordar los elementos jurídicos esenciales. No inventes siglas ni juegos de palabras sin relación clara con el concepto.
9. Identifica y evita confusiones con conceptos jurídicos próximos. Por ejemplo, no confundas ley marcial (régimen excepcional con intervención o autoridad militar sobre funciones civiles) con derecho o legislación militar (normas internas de las fuerzas armadas).

Responde ÚNICAMENTE con un objeto JSON válido sin texto adicional con el siguiente formato:
{{
    "definicion_tecnica": "...",
    "explicacion_sencilla": "...",
    "mnemotecnia": "..."
}}
""".strip()

        formato_json = {
            "type": "object",
            "properties": {
                "definicion_tecnica": {"type": "string"},
                "explicacion_sencilla": {"type": "string"},
                "mnemotecnia": {"type": "string"},
            },
            "required": list(GlossaryService.CAMPOS_REQUERIDOS),
            "additionalProperties": False,
        }

        url = f"{settings.OLLAMA_URL}/api/generate"

        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                ultimo_error = None
                for intento in range(1, 4):
                    prompt = prompt_base
                    if intento > 1:
                        prompt += (
                            "\n\nLa respuesta anterior fue inválida. Devuelve los tres campos completos, "
                            "respeta las longitudes mínimas y cierra correctamente el objeto JSON."
                        )
                    payload = {
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": formato_json,
                        "options": {"temperature": 0.1, "num_predict": 700},
                    }
                    logger.info(
                        "Enviando enriquecimiento de '%s' a Ollama (intento %s/3)...",
                        termino.palabra,
                        intento,
                    )
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    texto_respuesta = response.json().get("response", "").strip()
                    try:
                        datos_ia = GlossaryService._validar_datos_ia(
                            GlossaryService._extraer_json(texto_respuesta)
                        )
                        break
                    except (json.JSONDecodeError, TypeError, ValueError) as exc:
                        ultimo_error = exc
                        logger.warning(
                            "Respuesta inválida de Ollama para '%s' en intento %s: %s",
                            termino.palabra,
                            intento,
                            exc,
                        )
                else:
                    raise ValueError(f"Ollama no produjo una ficha válida: {ultimo_error}")

            if not termino.definicion_tecnica or termino.definicion_tecnica.strip() == "":
                termino.definicion_tecnica = datos_ia["definicion_tecnica"]
             
            termino.explicacion_sencilla = datos_ia["explicacion_sencilla"]
            termino.mnemotecnia = datos_ia["mnemotecnia"]

            return termino

        except httpx.TimeoutException:
            logger.error(f"Timeout al consultar Ollama para el término '{termino.palabra}'")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Tiempo de espera agotado al consultar el motor local Ollama."
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Ollama no generó una ficha válida para '%s': %s", termino.palabra, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "El modelo local no produjo una ficha jurídica válida después de varios intentos. "
                    "No se guardó información incompleta; vuelve a intentarlo."
                ),
            )
        except httpx.HTTPError as e:
            logger.error(f"Error HTTP al conectar con Ollama ({url}): {e}")
            raise OllamaServiceError(f"No se pudo establecer comunicación con Ollama en {settings.OLLAMA_URL}")
        except Exception as e:
            logger.error(f"Error inesperado en enriquecimiento: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al enriquecer el término jurídico: {str(e)}"
            )

glossary_service = GlossaryService()
