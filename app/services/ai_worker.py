import httpx
import base64
import itertools
import logging
import traceback
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.supabase import supabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [AI Worker] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

gemini_cycle = itertools.cycle(settings.GEMINI_API_KEYS) if settings.GEMINI_API_KEYS else None

def get_next_gemini_key():
    if not gemini_cycle:
        logger.error("Gemini API keys are not configured in .env")
        raise ValueError("Gemini API keys are not configured.")
    return next(gemini_cycle)

async def process_document_background(document_id: str, secure_url: str, extension: str):
    logger.info(f"====== STARTING AI PIPELINE FOR DOC: {document_id} ======")
    
    try:
        # 1. Download file bytes
        logger.info(f"Step 1: Downloading file from Cloudinary...")
        async with httpx.AsyncClient() as client:
            response = await client.get(secure_url, timeout=30.0)
            if response.status_code != 200:
                logger.error(f"Failed to fetch file from Cloudinary. HTTP Status: {response.status_code}")
                return
            file_bytes = response.content

        ext = str(extension).lower().replace(".", "")
        mime_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'webp': 'image/webp',
            'heic': 'image/heic'
        }
        
        if ext not in mime_map:
            logger.warning(f"Format '{ext}' not supported for OCR. Aborting pipeline.")
            return

        mime_type = mime_map[ext]
        base64_data = base64.b64encode(file_bytes).decode('utf-8')

        # 2. Extract text using Gemini 2.5 Flash
        logger.info(f"Step 2: Sending to Gemini 2.5 Flash for OCR Extraction...")
        extraction_key = get_next_gemini_key()
        extract_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={extraction_key}"
        
        extract_payload = {
            "contents": [{
                "parts": [
                    {"text": "Extract all readable text from this document accurately. If it contains tables or forms, try to preserve the layout. Do not add any conversational filler; output only the exact extracted text."},
                    {"inline_data": {
                        "mime_type": mime_type, 
                        "data": base64_data
                    }}
                ]
            }]
        }

        async with httpx.AsyncClient() as client:
            extract_res = await client.post(extract_url, json=extract_payload, timeout=60.0)
            
            if extract_res.status_code != 200:
                logger.error(f"Gemini Extraction API Error: {extract_res.status_code} - {extract_res.text}")
                return
                
            res_data = extract_res.json()
            
            try:
                extracted_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                logger.info(f"OCR successful! Extracted {len(extracted_text)} characters.")
            except KeyError:
                logger.warning(f"No valid text returned (Possible Safety Filter trigger): {res_data}")
                return

        if not extracted_text or not extracted_text.strip():
            logger.warning(f"Extracted text was completely empty.")
            return
            
        # 3. Split text
        logger.info("Step 3: Chunking text for embeddings...")
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
        chunks = splitter.split_text(extracted_text)
        logger.info(f"Split into {len(chunks)} chunks.")
        
        # 4. Embed with embedding-001
        logger.info("Step 4: Generating Vectors and saving to Supabase...")
        embed_key = get_next_gemini_key()
        embed_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={embed_key}"
        
        successful_embeddings = 0
        
        async with httpx.AsyncClient() as client:
            for i, chunk in enumerate(chunks):
                embed_payload = {
                    "model": "models/embedding-001",
                    "content": {
                        "parts": [{"text": chunk}]
                    }
                }
                
                embed_res = await client.post(embed_url, json=embed_payload, timeout=30.0)
                
                if embed_res.status_code != 200:
                    logger.error(f"Embedding API Error for chunk {i+1}: {embed_res.text}")
                    continue
                    
                embed_data = embed_res.json()
                vector_list = embed_data["embedding"]["values"]
                
                # Check for the expected 3072 dimensions based on your logs
                if len(vector_list) != 3072:
                    logger.error(f"Dimension mismatch! Expected 3072, got {len(vector_list)}")
                    continue
                
                # Format string explicitly for Postgres vector column
                vector_string = f"[{','.join(map(str, vector_list))}]"
                
                try:
                    supabase.table("document_embeddings").insert({
                        "document_id": document_id,
                        "raw_text": chunk,
                        "embedding": vector_string 
                    }).execute()
                    
                    successful_embeddings += 1
                except Exception as db_err:
                    logger.error(f" -> DB Insert failed for chunk {i+1}: {str(db_err)}")
            
        logger.info(f"====== PIPELINE COMPLETE: Indexed {successful_embeddings}/{len(chunks)} chunks for doc {document_id} ======")

    except Exception as e:
        logger.error(f"FATAL ERROR in pipeline for {document_id}: {str(e)}")
        logger.error(traceback.format_exc())