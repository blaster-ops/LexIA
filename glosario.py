import json
import os
import asyncio
from fastapi import HTTPException
from typing import List, Optional
from pydantic import BaseModel
import httpx

def print(*args, **kwargs):
    import sys
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


class Termino(BaseModel):
    palabra: str
    definicion_tecnica: str
    explicacion_sencilla: str = "Pendiente de generación"
    mnemotecnia: str = "Pendiente de generación"
    materia: str

class GestorGlosario:
    def __init__(self):
        # Ahora se usa el motor local de Ollama, no se requiere inicializar LLM globalmente.
        pass

    async def generar_enriquecimiento(self, termino: Termino):
        prompt_armado = f"""
        Actúa como LexIA, un experto en Derecho universal. Tu objetivo es proporcionar información jurídica rigurosa, clara y educativa. Para el término jurídico '{termino.palabra}' correspondiente a la materia '{termino.materia}':
        1. Genera una definición técnica formal y rigurosa.
        2. Genera una explicación muy sencilla para un estudiante de primer año.
        3. Crea una mnemotecnia divertida o fácil de recordar.
        
        Responde ÚNICAMENTE con un objeto JSON válido con las siguientes claves:
        {{
            "definicion_tecnica": "...",
            "explicacion_sencilla": "...",
            "mnemotecnia": "..."
        }}
        """

        try:
            print("DEBUG: Enviando solicitud de enriquecimiento a Ollama (gemma:7b)...")
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "gemma:7b",
                "prompt": prompt_armado.strip(),
                "stream": False,
                "options": {"temperature": 0.0}
            }
            
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                texto_respuesta = data.get("response", "").strip()
                
            print("DEBUG: Respuesta de enriquecimiento recibida de Ollama.")
            
            # Limpieza básica de markdown
            if "```json" in texto_respuesta:
                texto_respuesta = texto_respuesta.split("```json")[1].split("```")[0]
            elif "```" in texto_respuesta:
                texto_respuesta = texto_respuesta.split("```")[1].split("```")[0]
            
            datos_ia = json.loads(texto_respuesta)
            
            # Si la definición técnica viene vacía por parte del usuario, usamos la de la IA
            if not termino.definicion_tecnica:
                termino.definicion_tecnica = datos_ia.get("definicion_tecnica", termino.definicion_tecnica)
                
            termino.explicacion_sencilla = datos_ia.get("explicacion_sencilla", termino.explicacion_sencilla)
            termino.mnemotecnia = datos_ia.get("mnemotecnia", termino.mnemotecnia)
            
        except httpx.TimeoutException:
            print("\n[ERROR IA] Tiempo de espera agotado al consultar Ollama.\n")
            raise HTTPException(
                status_code=504, 
                detail="Tiempo de espera agotado al consultar el modelo local Ollama. El servidor está tardando demasiado. Intente de nuevo."
            )
        except Exception as e:
            print(f"\n[ERROR CRITICO IA] {e}\n")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno al comunicarse con Ollama: {str(e)}"
            )
