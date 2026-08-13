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
    """
    Devuelve la ruta absoluta a lexia_config.json.
    1. Si existe 'lexia_config.json' en la misma carpeta que el ejecutable/script, USAR ESE ARCHIVO.
       Esto garantiza que si el usuario edita el .json en Archivos de Programa (x86), la app lea esa IP.
    2. De lo contrario, usar %APPDATA%\\LexIA\\lexia_config.json.
    """
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    ruta_local = os.path.join(base, "lexia_config.json")

    # Si el archivo existe en la carpeta de instalación, esa es la fuente principal
    if os.path.exists(ruta_local):
        return ruta_local

    # Si no existe localmente, usar la carpeta AppData del usuario
    appdata = os.environ.get("APPDATA")
    if appdata:
        dir_appdata = os.path.join(appdata, "LexIA")
        os.makedirs(dir_appdata, exist_ok=True)
        return os.path.join(dir_appdata, "lexia_config.json")

    return ruta_local

def cargar_config():
    """
    Lee la configuración del servidor desde lexia_config.json.
    Si el archivo no existe o está corrupto, usa los valores por defecto.
    """
    ruta = obtener_ruta_config()
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            config = json.load(f)
        servidor = config.get("servidor", SERVIDOR_DEFAULT)
        puerto   = int(config.get("puerto",   PUERTO_DEFAULT))
        print(f"[LexIA] Configuración cargada desde {ruta}: {servidor}:{puerto}")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        servidor = SERVIDOR_DEFAULT
        puerto   = PUERTO_DEFAULT
        print(f"[LexIA] lexia_config.json no encontrado o inválido. Usando defaults: {servidor}:{puerto}")
        guardar_config(servidor, puerto)
    return servidor, puerto

def guardar_config(servidor: str, puerto: int):
    """Escribe lexia_config.json con permisos de usuario en AppData."""
    ruta = obtener_ruta_config()
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"servidor": servidor, "puerto": puerto}, f, indent=4)
        print(f"[LexIA] lexia_config.json guardado exitosamente en: {ruta}")
    except Exception as e:
        print(f"[LexIA] No se pudo guardar lexia_config.json en {ruta}: {e}")

def cambiar_ip_dialog(servidor_actual: str) -> str:
    """Muestra un diálogo gráfico para que el usuario ingrese la nueva IP fácilmente."""
    try:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        nueva_ip = simpledialog.askstring(
            "Servidor LexIA — Cambiar IP",
            "No se pudo conectar al servidor o deseas cambiar la IP.\n\nIngresa la dirección IP del Servidor LexIA:",
            initialvalue=servidor_actual
        )
        root.destroy()
        if nueva_ip and nueva_ip.strip():
            return nueva_ip.strip()
    except Exception:
        pass
    return servidor_actual

if __name__ == "__main__":
    # Permite pasar la IP como argumento o flag --config
    if "--config" in sys.argv:
        servidor_cur, puerto_cur = cargar_config()
        nueva_ip = cambiar_ip_dialog(servidor_cur)
        if nueva_ip:
            guardar_config(nueva_ip, puerto_cur)
            servidor, puerto = nueva_ip, puerto_cur
        else:
            servidor, puerto = servidor_cur, puerto_cur
    else:
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
