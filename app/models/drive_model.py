from pydantic import BaseModel
from typing import Optional

class FolderCreate(BaseModel):
    name: str
    parent_folder_id: Optional[str] = None

class FolderUpdate(BaseModel):
    # Make these Optional so you can rename WITHOUT moving, or vice versa
    name: Optional[str] = None
    parent_folder_id: Optional[str] = None

class FileUpdate(BaseModel):
    original_name: Optional[str] = None
    folder_id: Optional[str] = None