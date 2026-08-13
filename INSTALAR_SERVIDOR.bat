@echo off
chcp 65001 > NUL
title Instalador Automatizado del Servidor LexIA
echo ====================================================================
echo        LEXIA - INSTALADOR AUTOMATIZADO DEL SERVIDOR ENTERPRISE
echo ====================================================================
echo.
echo Este script configurara automaticamente el servidor LexIA en esta computadora.
echo.

:: 1. Verificar si existe Python
python --version > NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH de Windows.
    echo Por favor instala Python 3.10 o superior marcando la casilla Add Python to PATH.
    echo Descarga: https://www.python.org/downloads/
    pause
    exit /b
)

:: 2. Crear archivo .env si no existe
if not exist ".env" (
    echo [INFO] Creando archivo de configuracion .env por defecto...
    echo DB_HOST=localhost> .env
    echo DB_PORT=3306>> .env
    echo DB_USER=root>> .env
    echo DB_PASSWORD=>> .env
    echo DB_NAME=lexia_db>> .env
    echo ADMIN_USERNAME=2eigth>> .env
    echo ADMIN_PASSWORD=>> .env
    echo OLLAMA_URL=http://localhost:11434>> .env
    echo OLLAMA_MODEL=gemma:7b>> .env
    echo [OK] Archivo .env creado exitosamente.
)

:: 3. Crear entorno virtual venv
if not exist "venv" (
    echo [INFO] Creando entorno virtual Python...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b
    )
    echo [OK] Entorno virtual creado.
)

:: 4. Instalar librerias desde requirements.txt
echo [INFO] Instalando librerias desde requirements.txt...
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ocurrio un problema al instalar los paquetes de requirements.txt
    pause
    exit /b
)
echo [OK] Dependencias instaladas exitosamente.

:: 5. Descargar y cachear modelo de Embeddings HuggingFace
echo [INFO] Descargando modelo de Embeddings...
.\venv\Scripts\python.exe -c "from langchain_huggingface import HuggingFaceEmbeddings; emb = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2'); print('Caches de Embeddings OK!')"

:: 6. Verificar u Ollama Pull Gemma:7b
ollama --version > NUL 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Ollama detectado. Descargando modelo gemma:7b...
    ollama pull gemma:7b
) else (
    echo [ADVERTENCIA] Ollama no esta instalado en este sistema.
    echo Descargalo e instalalo desde https://ollama.com/
)

:: 7. Crear script de inicio INICIAR_SERVIDOR.bat
echo @echo off > INICIAR_SERVIDOR.bat
echo title Servidor LexIA - Ejecutandose >> INICIAR_SERVIDOR.bat
echo chcp 65001 ^> NUL >> INICIAR_SERVIDOR.bat
echo echo ============================================================ >> INICIAR_SERVIDOR.bat
echo echo             LEXIA - SERVIDOR INICIADO >> INICIAR_SERVIDOR.bat
echo echo ============================================================ >> INICIAR_SERVIDOR.bat
echo .\venv\Scripts\uvicorn main:app --reload --host 0.0.0.0 --port 8000 >> INICIAR_SERVIDOR.bat

echo.
echo ====================================================================
echo ¡INSTALACION Y CONFIGURACION DEL SERVIDOR COMPLETADA CON EXITO!
echo ====================================================================
echo.
echo Para iniciar el servidor en cualquier momento, haz doble clic en INICIAR_SERVIDOR.bat
echo.
pause
