import re
import os
from typing import Optional, List
from pypdf import PdfReader
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
import time

# Configuración global para persistencia
PERSIST_DIRECTORY = "./chroma_db"

def procesar_pdf(ruta_archivo: str) -> str:
    """Extrae texto simple (legacy) y procesa para RAG."""
    # Extracción simple para compatibilidad
    try:
        reader = PdfReader(ruta_archivo)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error lectura simple: {e}")
        texto_completo = ""
        
    # Procesamiento RAG
    print(f"Procesando RAG para: {ruta_archivo}")
    procesar_pdf_rag(ruta_archivo)
    
    return texto_completo

def procesar_pdf_rag(ruta_archivo: str):
    """Divide el PDF en chunks y guarda embeddings en ChromaDB."""
    try:
        loader = PyPDFLoader(ruta_archivo)
        documents = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        
        if chunks:
            # Usar embeddings de Google (requiere API KEY configurada en entorno)
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            
            # Guardar en disco
            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=PERSIST_DIRECTORY
            )
            # vectorstore.persist() # Chroma nuevo persiste auto
            print(f"Guardados {len(chunks)} fragmentos en ChromaDB.")
    except Exception as e:
        print(f"Error procesando RAG: {e}")

def buscar_palabra(texto: str, keyword: str, contexto: int = 100) -> Optional[str]:
    """Legacy: búsqueda de palabra por string matching."""
    if not texto or not keyword:
        return None
    match = re.search(re.escape(keyword), texto, re.IGNORECASE)
    if match:
        start = max(0, match.start() - contexto)
        end = min(len(texto), match.end() + contexto)
        fragmento = texto[start:end].replace('\n', ' ')
        return f"...{fragmento}..."
    return None

def buscar_contexto(query: str) -> str:
    """Busca fragmentos relevantes en la base de vectores."""
    # Permitimos que las excepciones (como DB no encontrada) se propaguen
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    vectorstore = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)
    
    # Recuperar top 3 fragmentos con reintento automático
    while True:
        try:
            docs = vectorstore.similarity_search(query, k=3)
            break
        except Exception as e:
            errores_limite = ["429", "RESOURCE_EXHAUSTED", "quota"]
            if any(err in str(e) for err in errores_limite):
                print("⚠️ Cuota excedida. Esperando 60 segundos para reintentar...")
                time.sleep(60)
            else:
                raise e
                
    contexto = "\n\n".join([d.page_content for d in docs])
    return contexto

def preguntar_al_tutor(pregunta: str) -> str:
    """
    Genera una respuesta utilizando RAG y el modelo Gemini 2.5 Flash.
    Propaga excepciones si falla la búsqueda de contexto.
    """
    contexto = buscar_contexto(pregunta)
    
    # Si no hay contexto, responder genéricamente o indicarlo
    if not contexto:
        contexto = "No se encontró información específica en los documentos proporcionados."

    template = """
    Eres LexIA, un experto en Derecho universal. Tu objetivo es proporcionar información jurídica rigurosa, clara y educativa para estudiantes y profesionales de cualquier país o institución. Utiliza el siguiente contexto para responder a la pregunta del estudiante.
    Si la respuesta no se encuentra en el contexto, indícalo, pero intenta ayudar con tu conocimiento general si es posible, aclarando que no viene del documento.
    
    Contexto:
    {contexto}
    
    Pregunta:
    {pregunta}
    """
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["contexto", "pregunta"]
    )
    
    # Usamos el modelo solicitado
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    
    chain = prompt | llm
    
    response = chain.invoke({"contexto": contexto, "pregunta": pregunta})
    return response.content.strip()
