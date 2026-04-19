from pydantic import BaseModel
from typing import Optional, List

class SessionCreate(BaseModel):
    title: Optional[str] = "New Industrial Session"
    document_id: Optional[str] = None

class SessionRename(BaseModel):
    title: str

class MessageAction(BaseModel):
    feedback: int # 1 for like, -1 for dislike, 0 for none

class ChatGenerationRequest(BaseModel):
    content: str
    session_id: str
    document_id: Optional[str] = None
    use_web_search: bool = False
    use_deep_think: bool = False