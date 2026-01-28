import json
import os
from typing import List, Optional
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

class Termino(BaseModel):
    palabra: str
    definicion_tecnica: str
    explicacion_sencilla: str = "Pendiente de generación"
    mnemotecnia: str = "Pendiente de generación"
    materia: str

class GestorGlosario:
    def __init__(self, archivo_db: str = "base_datos_glosario.json"):
        self.archivo_db = archivo_db
        try:
            # Se asume que GOOGLE_API_KEY está configurada en el entorno (main.py lo hace)
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        except Exception as e:
            print(f"\n🔴 ERROR CRÍTICO DE IA: {e}\n") # Agrega esto
            self.llm = None
        self.terminos: List[Termino] = self._cargar_datos()

    def _cargar_datos(self) -> List[Termino]:
        try:
            with open(self.archivo_db, "r", encoding="utf-8") as f:
                datos = json.load(f)
                return [Termino(**t) for t in datos]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _guardar_datos_archivo(self):
        with open(self.archivo_db, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in self.terminos], f, ensure_ascii=False, indent=4)

    def generar_enriquecimiento(self, termino: Termino):
        if not self.llm:
            print("No hay conexión con LLM, saltando enriquecimiento.")
            return

        template = """
        Actúa como LexIA, un experto en Derecho universal. Tu objetivo es proporcionar información jurídica rigurosa, clara y educativa. Para el término jurídico '{palabra}' correspondiente a la materia '{materia}':
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
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["palabra", "materia"]
        )
        
        chain = prompt | self.llm

        try:
            response = chain.invoke({"palabra": termino.palabra, "materia": termino.materia})
            texto_respuesta = response.content.strip()
            
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
            
        except Exception as e:
            print(f"\n🔴 ERROR CRÍTICO DE IA: {e}\n") # Agrega esto

    def guardar_termino(self, termino: Termino):
        """
        Enriquece el término con IA y lo guarda en la base de datos.
        """
        self.generar_enriquecimiento(termino)
        self.terminos.append(termino)
        self._guardar_datos_archivo()

    def obtener_terminos(self) -> List[Termino]:
        return self.terminos

    def limpiar_historial(self):
        """
        Elimina todos los términos del historial.
        """
        self.terminos = []
        self._guardar_datos_archivo()
