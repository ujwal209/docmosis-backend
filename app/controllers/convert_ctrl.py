import os
import uuid
import shutil
import cloudinary.uploader
import httpx
from datetime import datetime, timezone
from fastapi import HTTPException
from app.core.supabase import supabase
from app.core.config import settings
from app.models.convert_model import ConversionRequest

class ConvertController:
    # Direct mapping to iLovePDF REST API tools
    TOOL_MAP = {
        'word-to-pdf': 'officepdf',
        'image-to-pdf': 'imagepdf',
        'merge-pdf': 'merge',
        'split-pdf': 'split',
        'compress-pdf': 'compress',
        'lock-pdf': 'protect',
        'unlock-pdf': 'unlock'
    }

    @staticmethod
    def _get_auth_token():
        """Generates a fresh JWT auth token from iLovePDF"""
        res = httpx.post("https://api.ilovepdf.com/v1/auth", json={
            "public_key": settings.ILOVEPDF_PUBLIC_KEY
        }, timeout=10.0)
        
        if res.status_code != 200:
            raise Exception("Failed to authenticate with iLovePDF Engine.")
            
        return res.json()["token"]

    @staticmethod
    def process_conversion(user_id: str, payload: ConversionRequest):
        try:
            if payload.tool not in ConvertController.TOOL_MAP:
                raise HTTPException(status_code=400, detail="Invalid conversion tool selected.")
                
            ilovepdf_tool = ConvertController.TOOL_MAP[payload.tool]
            
            # Fetch the requested files from Supabase
            docs_res = supabase.table("documents").select("*").in_("id", payload.file_ids).eq("user_id", user_id).execute()
            documents = docs_res.data
            
            if not documents:
                raise HTTPException(status_code=404, detail="Files not found.")

            # Authenticate via REST
            token = ConvertController._get_auth_token()
            headers = {"Authorization": f"Bearer {token}"}
            
            new_files = []
            temp_dir = f"/tmp/docmosiss_conv_{uuid.uuid4()}" 
            os.makedirs(temp_dir, exist_ok=True)

            try:
                # ==========================================
                # BRANCH 1: MERGE (Combines all into one task)
                # ==========================================
                if ilovepdf_tool == 'merge':
                    # 1. Start Task
                    start_res = httpx.get(f"https://api.ilovepdf.com/v1/start/{ilovepdf_tool}", headers=headers, timeout=15.0)
                    if start_res.status_code != 200:
                        raise Exception("Failed to start iLovePDF task.")
                    
                    start_data = start_res.json()
                    server = start_data["server"]
                    task = start_data["task"]

                    # 2. Add files directly via their Cloudinary URLs
                    server_files = []
                    for doc in documents:
                        # FIX: Using the correct /v1/upload endpoint
                        add_res = httpx.post(f"https://{server}/v1/upload", headers=headers, json={
                            "task": task,
                            "cloud_file": doc["secure_url"]
                        }, timeout=30.0)
                        
                        if add_res.status_code != 200:
                            raise Exception(f"Upload to iLovePDF failed: {add_res.text}")
                            
                        add_data = add_res.json()
                        server_files.append({
                            "server_filename": add_data["server_filename"], 
                            "filename": doc["original_name"]
                        })

                    # 3. Execute the merge process
                    process_res = httpx.post(f"https://{server}/v1/process", headers=headers, json={
                        "task": task,
                        "tool": ilovepdf_tool,
                        "files": server_files
                    }, timeout=120.0)
                    
                    if process_res.status_code != 200:
                        error_msg = process_res.json().get('error', {}).get('message', 'Processing failed')
                        raise Exception(f"Process failed: {error_msg}")

                    # 4. Download result
                    download_res = httpx.get(f"https://{server}/v1/download/{task}", headers=headers, follow_redirects=True, timeout=120.0)
                    if download_res.status_code != 200:
                        raise Exception("Failed to download processed file from iLovePDF.")

                    local_path = os.path.join(temp_dir, "Merged_Document.pdf")
                    with open(local_path, "wb") as f:
                        f.write(download_res.content)
                    
                    # 5. Upload to Cloudinary & DB
                    new_file = ConvertController._upload_and_save(temp_dir, user_id, payload.target_folder_id, "Merged_Document")
                    new_files.append(new_file)

                # ==========================================
                # BRANCH 2: BATCH PROCESSING (One task per file)
                # ==========================================
                else:
                    for doc in documents:
                        # 1. Start Task
                        start_res = httpx.get(f"https://api.ilovepdf.com/v1/start/{ilovepdf_tool}", headers=headers, timeout=15.0)
                        if start_res.status_code != 200:
                            raise Exception("Failed to start iLovePDF task.")
                            
                        start_data = start_res.json()
                        server = start_data["server"]
                        task = start_data["task"]

                        # 2. Add file via Cloudinary URL
                        # FIX: Using the correct /v1/upload endpoint
                        add_res = httpx.post(f"https://{server}/v1/upload", headers=headers, json={
                            "task": task,
                            "cloud_file": doc["secure_url"]
                        }, timeout=30.0)
                        
                        if add_res.status_code != 200:
                            raise Exception(f"Upload to iLovePDF failed: {add_res.text}")
                            
                        add_data = add_res.json()
                        
                        file_obj = {
                            "server_filename": add_data["server_filename"], 
                            "filename": doc["original_name"]
                        }

                        # Apply password logic for UNLOCKING (Password applied to the file object)
                        if ilovepdf_tool == 'unlock' and payload.password:
                            file_obj["password"] = payload.password
                            
                        server_files = [file_obj]

                        # 3. Execute the process
                        process_payload = {
                            "task": task,
                            "tool": ilovepdf_tool,
                            "files": server_files
                        }
                        
                        # Apply password logic for LOCKING (Password applied to the root process payload)
                        if ilovepdf_tool == 'protect' and payload.password:
                            process_payload["password"] = payload.password

                        process_res = httpx.post(f"https://{server}/v1/process", headers=headers, json=process_payload, timeout=120.0)
                        
                        if process_res.status_code != 200:
                            error_msg = process_res.json().get('error', {}).get('message', 'Processing failed')
                            raise Exception(f"Process failed: {error_msg}")

                        # 4. Download result
                        sub_dir = os.path.join(temp_dir, str(uuid.uuid4()))
                        os.makedirs(sub_dir, exist_ok=True)
                        
                        download_res = httpx.get(f"https://{server}/v1/download/{task}", headers=headers, follow_redirects=True, timeout=120.0)
                        if download_res.status_code != 200:
                            raise Exception("Failed to download processed file from iLovePDF.")
                            
                        # Determine exact extension from the response headers
                        disp = download_res.headers.get("content-disposition", "")
                        ext = ".pdf"
                        if "filename=" in disp:
                            ext = "." + disp.split("filename=")[-1].strip('"').split(".")[-1]
                            
                        base_name = os.path.splitext(doc['original_name'])[0]
                        new_name_suffix = payload.tool.split("-")[0].capitalize()
                        
                        local_path = os.path.join(sub_dir, f"{base_name}_{new_name_suffix}{ext}")
                        with open(local_path, "wb") as f:
                            f.write(download_res.content)
                        
                        # 5. Upload to Cloudinary & DB
                        new_file = ConvertController._upload_and_save(sub_dir, user_id, payload.target_folder_id, f"{base_name}_{new_name_suffix}")
                        new_files.append(new_file)

                return {"message": f"{payload.tool.replace('-', ' ').title()} successful!", "files": new_files}

            finally:
                # ALWAYS clean up temp serverless storage
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

        except Exception as e:
            print(f"Error during conversion: {e}")
            raise HTTPException(status_code=400, detail=f"Conversion failed: {str(e)}")

    @staticmethod
    def _upload_and_save(directory: str, user_id: str, folder_id: str, base_name: str):
        """Helper to grab the file from a directory, upload to Cloudinary, and save to Supabase"""
        files_in_dir = os.listdir(directory)
        if not files_in_dir:
            raise Exception("No file generated.")
            
        local_filepath = os.path.join(directory, files_in_dir[0])
        filename = files_in_dir[0]
        extension = filename.split(".")[-1].lower() if "." in filename else ""
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            local_filepath, 
            resource_type="auto", 
            folder=f"docmosiss_users/{user_id}"
        )
        
        # Save to Supabase
        doc_data = {
            "user_id": user_id, 
            "cloudinary_id": upload_result["public_id"], 
            "secure_url": upload_result["secure_url"],
            "original_name": f"{base_name}.{extension}", 
            "extension": extension, 
            "file_size": upload_result.get("bytes", 0),
            "folder_id": folder_id, 
            "status": "Converted"
        }
        res = supabase.table("documents").insert(doc_data).execute()
        return res.data[0]