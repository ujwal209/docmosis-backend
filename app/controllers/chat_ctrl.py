import os
import sys
import itertools
import requests
import logging
from typing import Optional
from fastapi import HTTPException
from app.core.supabase import supabase
from app.models.chat_model import SessionCreate, ChatGenerationRequest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_groq import ChatGroq
from app.core.config import settings

# --- HARDCORE TERMINAL LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

groq_cycle = itertools.cycle(settings.GROQ_API_KEYS) if settings.GROQ_API_KEYS else None
gemini_cycle = itertools.cycle(settings.GEMINI_API_KEYS) if settings.GEMINI_API_KEYS else None

def get_next_groq_key():
    return next(groq_cycle)
    
def get_next_gemini_key():
    return next(gemini_cycle)

class ChatController:

    # ==========================================
    # SESSION MANAGEMENT
    # ==========================================
    
    @staticmethod
    def get_sessions(user_id: str):
        res = supabase.table("chat_sessions").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return res.data

    @staticmethod
    def create_session(user_id: str, payload: SessionCreate):
        res = supabase.table("chat_sessions").insert({
            "user_id": user_id, 
            "title": payload.title, 
            "document_id": payload.document_id
        }).execute()
        return res.data[0]

    @staticmethod
    def rename_session(user_id: str, session_id: str, title: str):
        res = supabase.table("chat_sessions").update({"title": title}).eq("id", session_id).eq("user_id", user_id).execute()
        return res.data[0]

    @staticmethod
    def archive_session(user_id: str, session_id: str):
        supabase.table("chat_sessions").update({"is_archived": True}).eq("id", session_id).eq("user_id", user_id).execute()
        return {"status": "archived"}

    @staticmethod
    def unarchive_session(user_id: str, session_id: str):
        supabase.table("chat_sessions").update({"is_archived": False}).eq("id", session_id).eq("user_id", user_id).execute()
        return {"status": "unarchived"}

    @staticmethod
    def delete_session(user_id: str, session_id: str):
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        supabase.table("chat_sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()
        return {"status": "deleted"}

    @staticmethod
    def get_messages(session_id: str):
        res = supabase.table("chat_messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
        return res.data

    @staticmethod
    def update_feedback(message_id: str, feedback: int):
        supabase.table("chat_messages").update({"feedback": feedback}).eq("id", message_id).execute()
        return {"status": "feedback updated"}

    # ==========================================
    # CORE AI & GLOBAL/SPECIFIC RAG LOGIC
    # ==========================================

    @staticmethod
    async def process_chat(user_id: str, payload: ChatGenerationRequest):
        logger.info(f"--- NEW CHAT REQUEST INITIATED | Session: {payload.session_id} ---")
        
        # 1. Save User Message
        supabase.table("chat_messages").insert({
            "session_id": payload.session_id, 
            "role": "user", 
            "content": payload.content
        }).execute()

        # 2. Fetch Chat History
        history_res = supabase.table("chat_messages").select("role, content")\
            .eq("session_id", payload.session_id)\
            .order("created_at", desc=False).execute()
        
        lc_messages = []
        for msg in history_res.data:
            if msg["role"] == "user": lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant": lc_messages.append(AIMessage(content=msg["content"]))

        # 3. GLOBAL OR SPECIFIC RAG PIPELINE
        system_prompt = ""
        rag_context = ""
        
        target_mode = f"Specific Doc ({payload.document_id})" if payload.document_id else "GLOBAL WORKSPACE (All Docs)"
        logger.info(f"[RAG] Pipeline Triggered. Mode: {target_mode}")

        try:
            # FIX: EXACT model name "gemini-embedding-001" exactly as requested
            embed_key = get_next_gemini_key()
            embed_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={embed_key}"
            
            logger.info(f"[RAG-GEMINI] Vectorizing: '{payload.content}'")
            embed_res = requests.post(embed_url, json={
                "model": "gemini-embedding-001",
                "content": {"parts": [{"text": payload.content}]}
            }, timeout=10.0)
            
            if embed_res.status_code == 200:
                query_vector = embed_res.json()["embedding"]["values"]
                vector_string = f"[{','.join(map(str, query_vector))}]"
                logger.info(f"[RAG-GEMINI] Success! Generated vector.")
                
                # BRANCH: Search 1 Doc vs Search ALL Docs
                if payload.document_id:
                    logger.info(f"[RAG-SUPABASE] Executing 'match_documents' for doc_id: {payload.document_id}")
                    rpc_res = supabase.rpc('match_documents', {
                        'query_embedding': vector_string,
                        'match_threshold': 0.15, 
                        'match_count': 6,
                        'p_document_id': payload.document_id
                    }).execute()
                else:
                    logger.info(f"[RAG-SUPABASE] Executing 'match_user_documents' for entire workspace of user: {user_id}")
                    rpc_res = supabase.rpc('match_user_documents', {
                        'query_embedding': vector_string,
                        'match_threshold': 0.15, 
                        'match_count': 10,  
                        'p_user_id': user_id
                    }).execute()
                
                if rpc_res.data and len(rpc_res.data) > 0:
                    logger.info(f"[RAG-SUPABASE] HIT! Found {len(rpc_res.data)} matching chunks.")
                    rag_context = "\n\n".join([chunk['raw_text'] for chunk in rpc_res.data])
                    
                    snippet = rag_context[:100].replace('\n', ' ')
                    logger.info(f"[RAG-CONTEXT] Snippet: '{snippet}...'")
                    
                    system_prompt = f"""You are Docmosiss, an intelligent enterprise document AI.
                    
CRITICAL DIRECTIVES:
1. Base your answer ONLY on the DOCUMENT CONTEXT provided below.
2. If the user asks for a summary, or what the document is about, summarize the context naturally.
3. If the user asks a specific question and the answer is absolutely NOT in the context, reply exactly with: "I cannot find the answer to this in your documents."
4. DO NOT use outside knowledge. DO NOT guess. DO NOT hallucinate.
5. Format your response cleanly using Markdown.

--- DOCUMENT CONTEXT START ---
{rag_context}
--- DOCUMENT CONTEXT END ---
"""
                else:
                    logger.warning(f"[RAG-SUPABASE] MISS! Zero chunks matched.")
                    system_prompt = """You are Docmosiss, an intelligent document engine. 
CRITICAL DIRECTIVE: NEVER say "I am a large language model" or "I don't have access to your files".
Tell the user exactly this: "I searched through your documents, but my vector engine didn't find a direct match for that query. Could you try rephrasing or asking about a specific topic?"""
            else:
                logger.error(f"[RAG-GEMINI] FAILED! {embed_res.text}")
                raise Exception("Embedding generation failed.")
                
        except Exception as e:
            logger.error(f"[RAG-CRITICAL ERROR] Pipeline crashed: {str(e)}")
            system_prompt = "You are Docmosiss. Inform the user that there was a temporary system error connecting to the vector database, and ask them to try again."

        # 4. Groq Inference Engine
        logger.info(f"[LLM] Triggering Groq Inference...")
        model_name = "llama-3.3-70b-versatile" if getattr(payload, 'use_deep_think', False) else "llama-3.1-8b-instant"
        llm = ChatGroq(
            model=model_name, 
            api_key=get_next_groq_key(), 
            temperature=0.0
        )

        final_messages = [SystemMessage(content=system_prompt)] + lc_messages
        response = llm.invoke(final_messages)
        ai_response = response.content
        logger.info(f"[LLM] Success! Generated {len(ai_response)} characters.")

        # 5. Save Assistant Message & Finalize
        supabase.table("chat_messages").insert({
            "session_id": payload.session_id, 
            "role": "assistant", 
            "content": ai_response
        }).execute()
        
        supabase.table("chat_sessions").update({"updated_at": "now()"}).eq("id", payload.session_id).execute()

        logger.info(f"--- CHAT REQUEST COMPLETE ---")
        return {"role": "assistant", "content": ai_response}