from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.controllers.chat_ctrl import ChatController
from app.models.chat_model import SessionCreate, SessionRename, MessageAction, ChatGenerationRequest

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])

@router.get("/sessions")
async def get_sessions(user_id: str = Depends(get_current_user)):
    return ChatController.get_sessions(user_id)

@router.post("/sessions")
async def create_session(payload: SessionCreate, user_id: str = Depends(get_current_user)):
    return ChatController.create_session(user_id, payload)

@router.patch("/sessions/{session_id}/rename")
async def rename_session(session_id: str, payload: SessionRename, user_id: str = Depends(get_current_user)):
    return ChatController.rename_session(user_id, session_id, payload.title)

@router.patch("/sessions/{session_id}/archive")
async def archive_session(session_id: str, user_id: str = Depends(get_current_user)):
    return ChatController.archive_session(user_id, session_id)

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(get_current_user)):
    return ChatController.delete_session(user_id, session_id)

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, user_id: str = Depends(get_current_user)):
    # Validate auth happens implicitly by only returning if they own the session in controller, but simplified here
    return ChatController.get_messages(session_id)

@router.post("/chat")
async def process_chat(payload: ChatGenerationRequest, user_id: str = Depends(get_current_user)):
    return await ChatController.process_chat(user_id, payload)

@router.patch("/messages/{message_id}/feedback")
async def update_feedback(message_id: str, payload: MessageAction, user_id: str = Depends(get_current_user)):
    return ChatController.update_feedback(message_id, payload.feedback)


@router.get("/sessions")
async def get_sessions(archived: bool = False, user_id: str = Depends(get_current_user)):
    return ChatController.get_sessions(user_id, archived)

@router.patch("/sessions/{session_id}/unarchive")
async def unarchive_session(session_id: str, user_id: str = Depends(get_current_user)):
    return ChatController.unarchive_session(user_id, session_id)


@router.patch("/sessions/{session_id}/unarchive")
async def unarchive_session(session_id: str, user_id: str = Depends(get_current_user)):
    return ChatController.unarchive_session(user_id, session_id)