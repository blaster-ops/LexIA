import re
import os
from typing import Optional, List
from pypdf import PdfReader
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import httpx
import time

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




def procesar_pdf(ruta_archivo: str, username: str) -> str:
    """Extrae texto simple (legacy) y procesa para RAG."""
    # Extracción simple para compatibilidad
    try:
        reader = PdfReader(ruta_archivo)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"Error lectura simple: {e}")
        texto_completo = ""
        
    # Procesamiento RAG
    print(f"Procesando RAG para: {ruta_archivo}")
    procesar_pdf_rag(ruta_archivo, username)
    
    return texto_completo

def procesar_pdf_rag(ruta_archivo: str, username: str):
    """Divide el PDF en chunks y guarda embeddings en ChromaDB."""
    try:
        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()
        
        # Limpiar y normalizar el metadata 'source' para búsquedas posteriores
        filename = os.path.basename(ruta_archivo)
        if filename.startswith("temp_"):
            filename = filename[5:]
            
        for doc in documents:
            doc.metadata['source'] = filename
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        print(f"[OK] Se leyeron y cortaron {len(chunks)} fragmentos del PDF.")
        
        if chunks:
            # Usar embeddings locales de HuggingFace
            embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
            
            # Guardar en disco en lotes
            batch_size = 80
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            for i in range(0, len(chunks), batch_size):
                lote = chunks[i:i + batch_size]
                num_lote = (i // batch_size) + 1
                
                if num_lote == 1:
                    vectorstore = Chroma.from_documents(
                        documents=lote,
                        embedding=embeddings,
                        persist_directory=f"./data/users/{username}/chroma_db"
                    )
                else:
                    vectorstore.add_documents(lote)
                    
                if num_lote < total_batches:
                    print(f"Lote {num_lote}/{total_batches} guardado, esperando 60 segundos...")
                    time.sleep(60)
                else:
                    print(f"Lote {num_lote}/{total_batches} guardado.")
                    
            print(f"Guardados {len(chunks)} fragmentos en ChromaDB en lotes de {batch_size}.")
    except Exception as e:
        print(f"Error procesando RAG: {e}")

def buscar_literal_en_pdf(ruta_archivo: str, keyword: str) -> str:
    """Búsqueda literal (Lexical Search) exacta en PDF usando PyMuPDF."""
    import fitz # PyMuPDF
    if not os.path.exists(ruta_archivo):
        return ""
        
    doc = fitz.open(ruta_archivo)
    coincidencias = []
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    
    for page_num, page in enumerate(doc):
        texto = page.get_text()
        
        for match in pattern.finditer(texto):
            start = max(0, match.start() - 150)
            end = min(len(texto), match.end() + 150)
            
            contexto_str = texto[start:end].replace('\n', ' ').strip()
            
            resultado = f"Página {page_num + 1}: ...{contexto_str}..."
            coincidencias.append(resultado)
            
            if len(coincidencias) >= 20:
                break
        if len(coincidencias) >= 20:
            break
            
    doc.close()
    
    if not coincidencias:
        return ""
        
    return "<br><br>".join(coincidencias)

def buscar_contexto(query: str, username: str, filename_filter: Optional[str] = None) -> str:
    """Busca fragmentos relevantes en la base de vectores."""
    # Permitimos que las excepciones (como DB no encontrada) se propaguen
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", model_kwargs={'local_files_only': True})
    user_chroma_dir = f"./data/users/{username}/chroma_db"
    vectorstore = Chroma(persist_directory=user_chroma_dir, embedding_function=embeddings)
    
    # Configurar retriever
    search_kwargs = {'k': 4}
    if filename_filter:
        search_kwargs['filter'] = {'source': filename_filter}
        
    retriever = vectorstore.as_retriever(search_type='similarity', search_kwargs=search_kwargs)
    
    # C-3: Recuperar fragmentos con reintento limitado (máx. 3 intentos)
    errores_limite = ["429", "RESOURCE_EXHAUSTED", "quota"]
    max_reintentos = 3
    docs_filtrados = []
    for intento in range(max_reintentos):
        try:
            docs_filtrados = retriever.invoke(query)
            break
        except Exception as e:
            if any(err in str(e) for err in errores_limite) and intento < max_reintentos - 1:
                print(f"[AVISO] Cuota excedida (intento {intento + 1}/{max_reintentos}). Esperando 60 segundos...")
                time.sleep(60)
            else:
                raise e
    
    print(f"[BUSQUEDA] Se devolvera(n) {len(docs_filtrados)} documento(s) mas cercanos.")
    if docs_filtrados:
        print(f"[FRAGMENTO] Fragmento 1 recuperado: {docs_filtrados[0].page_content[:200]}...")

    contexto = "\n\n".join([d.page_content for d in docs_filtrados])
    return contexto

async def preguntar_al_tutor(pregunta: str, username: str, filename_filter: Optional[str] = None) -> str:
    """
    Genera una respuesta utilizando RAG y el modelo local Ollama (gemma:7b).
    Propaga excepciones si falla la búsqueda de contexto.
    """
    from starlette.concurrency import run_in_threadpool
    from langchain_community.llms import Ollama
    from langchain_core.prompts import PromptTemplate
    
    contexto = await run_in_threadpool(buscar_contexto, pregunta, username, filename_filter)
    
    # Si no hay contexto, responder genéricamente o indicarlo
    if not contexto:
        contexto = "No se encontró información específica en los documentos proporcionados."

    template_str = """
Eres LexIA, un experto en Derecho universal. Tu objetivo es proporcionar información jurídica rigurosa, clara y educativa para estudiantes y profesionales de cualquier país o institución. Utiliza el siguiente contexto para responder a la pregunta del estudiante.
Si la respuesta no se encuentra en el contexto, indícalo, pero intenta ayudar con tu conocimiento general si es posible, aclarando que no viene del documento.

Contexto:
{contexto}

Pregunta:
{pregunta}
"""
    
    print("DEBUG: Enviando pregunta RAG a Ollama (gemma:7b)...")
    
    try:
        # Configuración estricta del LLM como fue solicitado
        llm = Ollama(model="gemma:7b", temperature=0.0)
        
        # Configurar la cadena
        prompt = PromptTemplate(
            template=template_str,
            input_variables=["contexto", "pregunta"]
        )
        cadena = prompt | llm
        
        # Ejecutar invoke con contexto
        respuesta = await run_in_threadpool(cadena.invoke, {"contexto": contexto, "pregunta": pregunta})
            
        print("DEBUG: Respuesta RAG de Ollama recibida.")
        return respuesta.strip()
    except Exception as e:
        print(f"Error detallado: {e}")
        raise Exception(f"Error interno al comunicarse con Ollama: {str(e)}")
