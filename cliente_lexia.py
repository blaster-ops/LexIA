"""
=============================================================================
Proyecto: LexIA - Cliente Ligero
Autor y Titular de Propiedad Intelectual: José Miguel Tapia Adán
Fecha de Creación: Mayo 2026
Institución: Universidad Tecnológica de Tehuacán (UTT)

Descripción:
    Este script es el cliente ligero del sistema LexIA en arquitectura
    cliente-servidor. Su única responsabilidad es abrir una ventana nativa
    que se conecta al servidor remoto. No arranca FastAPI, Uvicorn, Ollama
    ni ChromaDB localmente.

    La IP y puerto del servidor se leen desde 'lexia_config.json', ubicado
    en la misma carpeta que este archivo. Para cambiar el servidor, edita
    ese archivo con el Bloc de notas y reinicia el cliente.

Aviso Legal:
    El presente código es una obra original. El acceso al mismo se otorga
    exclusivamente para fines de evaluación académica. Queda estrictamente
    prohibida su copia, modificación, distribución, o apropiación por parte
    de terceros sin autorización expresa.
=============================================================================
"""

import webview
import json
import os
import sys

# --- VALORES POR DEFECTO ---
SERVIDOR_DEFAULT = "192.168.68.63"
PUERTO_DEFAULT   = 8000

def obtener_ruta_config():
    """Devuelve la ruta absoluta a lexia_config.json, junto al .exe o al .py."""
    if getattr(sys, 'frozen', False):
        # Ejecutando como .exe compilado con PyInstaller
        base = os.path.dirname(sys.executable)
    else:
        # Ejecutando como script .py
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "lexia_config.json")

def cargar_config():
    """
    Lee la configuración del servidor desde lexia_config.json.
    Si el archivo no existe o está corrupto, usa los valores por defecto
    y recrea el archivo automáticamente.
    """
    ruta = obtener_ruta_config()
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            config = json.load(f)
        servidor = config.get("servidor", SERVIDOR_DEFAULT)
        puerto   = int(config.get("puerto",   PUERTO_DEFAULT))
        print(f"[LexIA] Configuración cargada: {servidor}:{puerto}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        # Archivo ausente o inválido → usar defaults y recrear el archivo
        servidor = SERVIDOR_DEFAULT
        puerto   = PUERTO_DEFAULT
        print(f"[LexIA] lexia_config.json no encontrado o inválido. Usando valores por defecto: {servidor}:{puerto}")
        guardar_config(servidor, puerto)
    return servidor, puerto

def guardar_config(servidor: str, puerto: int):
    """Escribe (o sobreescribe) lexia_config.json con los valores dados."""
    ruta = obtener_ruta_config()
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"servidor": servidor, "puerto": puerto}, f, indent=4)
        print(f"[LexIA] lexia_config.json guardado en: {ruta}")
    except Exception as e:
        print(f"[LexIA] No se pudo guardar lexia_config.json: {e}")

if __name__ == "__main__":
    servidor, puerto = cargar_config()
    url_servidor = f"http://{servidor}:{puerto}"

    print(f"[LexIA] Conectando a: {url_servidor}")

    webview.create_window(
        title="LexIA - Emerald Systems",
        url=url_servidor,
        width=1280,
        height=800
    )
    webview.start()
