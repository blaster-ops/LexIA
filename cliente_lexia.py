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

Aviso Legal:
    El presente código es una obra original. El acceso al mismo se otorga
    exclusivamente para fines de evaluación académica. Queda estrictamente
    prohibida su copia, modificación, distribución, o apropiación por parte
    de terceros sin autorización expresa.
=============================================================================
"""

import webview

if __name__ == "__main__":
    webview.create_window(
        title="LexIA - Emerald Systems",
        url="http://192.168.68.63:8000",
        width=1280,
        height=800
    )
    webview.start()
