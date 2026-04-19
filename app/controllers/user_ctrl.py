from fastapi import HTTPException
from app.core.supabase import supabase
from app.models.user_model import OnboardingRequest

class UserController:
    @staticmethod
    def complete_onboarding(user_id: str, payload: OnboardingRequest):
        try:
            # Package the data to update
            data = {
                "user_type": payload.user_type,
                "primary_use_case": payload.primary_use_case,
                "bio": payload.bio,
                "onboarding_completed": True
            }
            
            # Update the profile in the Supabase public.profiles table
            response = supabase.table("profiles").update(data).eq("id", user_id).execute()
            
            # If no data returns, the profile didn't exist
            if not response.data:
                raise HTTPException(status_code=404, detail="User profile not found. Did the database trigger run?")
                
            return {
                "message": "Onboarding completed successfully.", 
                "profile": response.data[0]
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))