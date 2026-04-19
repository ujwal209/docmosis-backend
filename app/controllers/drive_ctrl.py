import os
import uuid
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, BackgroundTasks
from app.core.supabase import supabase
from app.models.drive_model import FolderCreate, FolderUpdate, FileUpdate
from app.services.ai_worker import process_document_background

class DriveController:

    # ==========================================
    # FOLDER OPERATIONS
    # ==========================================
    
    @staticmethod
    def create_folder(user_id: str, payload: FolderCreate):
        try:
            parent_id = None if payload.parent_folder_id in ["root", None] else payload.parent_folder_id
            res = supabase.table("folders").insert({
                "user_id": user_id,
                "name": payload.name,
                "parent_folder_id": parent_id
            }).execute()
            return {"message": "Folder created", "folder": res.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create folder: {str(e)}")

    @staticmethod
    def update_folder(user_id: str, folder_id: str, payload: FolderUpdate):
        try:
            update_data = {}
            if payload.name is not None:
                update_data["name"] = payload.name
            if payload.parent_folder_id is not None:
                update_data["parent_folder_id"] = None if payload.parent_folder_id == "root" else payload.parent_folder_id
                
            if not update_data:
                return {"message": "No updates provided"}

            res = supabase.table("folders").update(update_data).eq("id", folder_id).eq("user_id", user_id).execute()
            
            if not res.data:
                raise HTTPException(status_code=404, detail="Folder not found")
                
            return {"message": "Folder updated successfully", "folder": res.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to update folder: {str(e)}")

    @staticmethod
    def delete_folder(user_id: str, folder_id: str):
        try:
            res = supabase.table("folders").delete().eq("id", folder_id).eq("user_id", user_id).execute()
            if not res.data:
                raise HTTPException(status_code=404, detail="Folder not found")
            return {"message": "Folder deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to delete folder: {str(e)}")


    # ==========================================
    # FILE OPERATIONS
    # ==========================================

    @staticmethod
    def upload_file(user_id: str, file: UploadFile, folder_id: str, background_tasks: BackgroundTasks):
        try:
            contents = file.file.read()
            original_name = file.filename
            extension = original_name.split(".")[-1].lower() if "." in original_name else ""
            
            # --- CLOUDINARY UPLOAD FIX ---
            # Try 'auto' first. For PDFs, Cloudinary assigns 'image' so it opens in the browser natively!
            try:
                upload_result = cloudinary.uploader.upload(
                    contents, 
                    resource_type="auto", 
                    folder=f"docmosiss_users/{user_id}"
                )
            except Exception as e:
                # If it fails (usually because it's a locked PDF), fallback to raw.
                if "Password-protected" in str(e) or extension == "pdf":
                    upload_result = cloudinary.uploader.upload(
                        contents, 
                        resource_type="raw", 
                        folder=f"docmosiss_users/{user_id}",
                        format=extension
                    )
                else:
                    raise e

            secure_url = upload_result.get("secure_url")
            
            doc_data = {
                "user_id": user_id,
                "cloudinary_id": upload_result.get("public_id"),
                "secure_url": secure_url,
                "original_name": original_name,
                "extension": extension,
                "file_size": upload_result.get("bytes", 0),
                "folder_id": folder_id if folder_id and folder_id != "root" else None,
                "status": "uploaded"
            }
            
            res = supabase.table("documents").insert(doc_data).execute()
            saved_doc = res.data[0]
            doc_id = saved_doc["id"]

            background_tasks.add_task(
                process_document_background, 
                document_id=doc_id, 
                secure_url=secure_url, 
                extension=extension
            )

            return {"message": "File uploaded successfully. AI indexing in background.", "file": saved_doc}

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")

    @staticmethod
    def update_file(user_id: str, file_id: str, payload: FileUpdate):
        try:
            update_data = {}
            if payload.original_name is not None:
                update_data["original_name"] = payload.original_name
            if payload.folder_id is not None:
                update_data["folder_id"] = None if payload.folder_id == "root" else payload.folder_id

            if not update_data:
                return {"message": "No updates provided"}

            res = supabase.table("documents").update(update_data).eq("id", file_id).eq("user_id", user_id).execute()
            if not res.data:
                raise HTTPException(status_code=404, detail="File not found")
                
            return {"message": "File updated successfully", "file": res.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to update file: {str(e)}")

    @staticmethod
    def delete_file(user_id: str, file_id: str):
        try:
            file_res = supabase.table("documents").select("cloudinary_id, extension").eq("id", file_id).eq("user_id", user_id).execute()
            if not file_res.data:
                raise HTTPException(status_code=404, detail="File not found")
                
            file_data = file_res.data[0]
            
            r_type = "raw" if file_data["extension"] == "pdf" else "image"
            try:
                cloudinary.uploader.destroy(file_data["cloudinary_id"], resource_type=r_type)
            except Exception as cloud_err:
                print(f"Cloudinary deletion warning: {cloud_err}")

            supabase.table("documents").delete().eq("id", file_id).execute()
            
            return {"message": "File deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to delete file: {str(e)}")


    # ==========================================
    # DIRECTORY FETCHING
    # ==========================================

    @staticmethod
    def get_directory_contents(user_id: str, folder_id: str = None):
        try:
            if folder_id == "root" or not folder_id:
                folder_filter = "is.null"
            else:
                folder_filter = f"eq.{folder_id}"

            folders_res = supabase.table("folders") \
                .select("*") \
                .eq("user_id", user_id) \
                .filter("parent_folder_id", folder_filter.split(".")[0], folder_filter.split(".")[1] if "." in folder_filter else None) \
                .order("created_at", desc=True) \
                .execute()

            files_res = supabase.table("documents") \
                .select("*") \
                .eq("user_id", user_id) \
                .filter("folder_id", folder_filter.split(".")[0], folder_filter.split(".")[1] if "." in folder_filter else None) \
                .order("created_at", desc=True) \
                .execute()

            return {
                "folders": folders_res.data,
                "files": files_res.data
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch directory contents: {str(e)}")

    @staticmethod
    def get_file(user_id: str, file_id: str):
        try:
            res = supabase.table("documents").select("*").eq("id", file_id).eq("user_id", user_id).execute()
            if not res.data:
                raise HTTPException(status_code=404, detail="File not found")
            return res.data[0]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch file: {str(e)}")