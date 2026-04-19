from pydantic import BaseModel
from typing import List, Optional

class ConversionRequest(BaseModel):
    tool: str  
    file_ids: List[str]  
    target_folder_id: Optional[str] = None  
    password: Optional[str] = None # NEW: Added for Lock/Unlock