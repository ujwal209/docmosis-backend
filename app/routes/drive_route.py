from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from app.core.security import get_current_user
from app.controllers.drive_ctrl import DriveController
from app.models.drive_model import FolderCreate, FolderUpdate, FileUpdate

router = APIRouter(prefix="/drive", tags=["Drive Management"])

# --- FOLDERS ---

@router.post("/folders")
async def create_folder(payload: FolderCreate, user_id: str = Depends(get_current_user)):
    return DriveController.create_folder(user_id, payload)

@router.patch("/folders/{folder_id}")
async def update_folder(folder_id: str, payload: FolderUpdate, user_id: str = Depends(get_current_user)):
    return DriveController.update_folder(user_id, folder_id, payload)

@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, user_id: str = Depends(get_current_user)):
    return DriveController.delete_folder(user_id, folder_id)


# --- FILES ---

@router.post("/files/upload")
async def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    folder_id: Optional[str] = Form(None), 
    user_id: str = Depends(get_current_user)
):
    # Passes the background task to the controller so AI indexing can happen asynchronously
    return DriveController.upload_file(user_id, file, folder_id, background_tasks)

@router.patch("/files/{file_id}")
async def update_file(file_id: str, payload: FileUpdate, user_id: str = Depends(get_current_user)):
    return DriveController.update_file(user_id, file_id, payload)

@router.delete("/files/{file_id}")
async def delete_file(file_id: str, user_id: str = Depends(get_current_user)):
    return DriveController.delete_file(user_id, file_id)


# --- DIRECTORY FETCHING ---

@router.get("/contents")
async def get_contents(folder_id: Optional[str] = None, user_id: str = Depends(get_current_user)):
    return DriveController.get_directory_contents(user_id, folder_id)
    
@router.get("/files/{file_id}")
async def get_file(file_id: str, user_id: str = Depends(get_current_user)):
    return DriveController.get_file(user_id, file_id)