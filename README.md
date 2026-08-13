# LexIA — Asistente Jurídico Inteligente

LexIA es una aplicación cliente-servidor para despachos jurídicos. Permite administrar usuarios, indexar documentos PDF por usuario, realizar búsquedas literales, consultar un asistente RAG local con Ollama y mantener un diccionario jurídico.

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior.
- MySQL o MariaDB.
- Ollama con el modelo configurado (por defecto `gemma:7b`).
- El modelo de embeddings `sentence-transformers/all-MiniLM-L6-v2`.

## Configuración

La configuración privada se lee desde `.env`. Este archivo no debe compartirse ni incluirse en instaladores o respaldos públicos.

Variables principales:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=lexia_db
ADMIN_USERNAME=abogado
ADMIN_PASSWORD=una_contraseña_segura
LEXIA_SECRET_KEY=una_clave_larga_y_aleatoria
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma:7b
MAX_UPLOAD_SIZE_MB=50
```

## Instalación y ejecución

Para preparar el servidor se puede utilizar `INSTALAR_SERVIDOR.bat`. Para iniciarlo:

```powershell
.\INICIAR_SERVIDOR.bat
```

El servidor queda disponible en el puerto `8000`. El cliente ligero obtiene la dirección mediante `lexia_config.json`.

## Datos persistentes

- Usuarios y fichas del diccionario: MySQL (`lexia_db`).
- PDF y base vectorial: `data/users/<usuario>/`.
- Configuración privada: `.env`.

Los PDF originales son la fuente verificable. ChromaDB contiene los fragmentos derivados utilizados por el flujo RAG.

## Pruebas rápidas

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m compileall -q main.py cliente_lexia.py app tests
```

Antes de una entrega conviene comprobar inicio de sesión, MFA, carga y listado de PDF, Lupa Legal, Consultor IA, diccionario y administración de usuarios.

## Seguridad operativa

- No usar las credenciales predeterminadas en una instalación real.
- No compartir `.env` ni exportaciones SQL.
- Aceptar únicamente documentos conocidos y mantener un respaldo de MySQL y `data/`.
- Las respuestas generadas por IA deben ser revisadas por un profesional; no sustituyen asesoría jurídica.
