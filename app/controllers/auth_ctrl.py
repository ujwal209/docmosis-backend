import random
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.core.supabase import supabase
from app.models.auth_model import SignupRequest, VerifyOTPRequest, LoginRequest, ResendOTPRequest
from app.utils.email import send_otp_email

def generate_otp():
    """Generates a secure 6-digit verification code."""
    return str(random.randint(100000, 999999))

class AuthController:
    @staticmethod
    def signup_user(payload: SignupRequest):
        try:
            # 1. Check if user already exists in custom profiles to avoid double signup
            existing = supabase.table("profiles").select("id").eq("email", payload.email).execute()
            if existing.data:
                raise HTTPException(status_code=400, detail="Email already registered. Please log in.")

            # 2. Let Supabase handle the password hashing and hidden user creation
            auth_res = supabase.auth.sign_up({
                "email": payload.email,
                "password": payload.password,
            })
            
            user = auth_res.user
            if not user:
                raise HTTPException(status_code=400, detail="Signup failed at provider level.")

            # 3. Create the row in your custom public.profiles table
            supabase.table("profiles").insert({
                "id": user.id,
                "email": payload.email,
                "full_name": payload.full_name,
                "is_verified": False,
                "onboarding_completed": False
            }).execute()

            # 4. Generate and store the manual OTP
            otp = generate_otp()
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            
            supabase.table("otp_verifications").insert({
                "email": payload.email,
                "otp_code": otp,
                "type": "signup",
                "status": "pending",
                "expires_at": expires_at,
                "user_id": user.id
            }).execute()

            # 5. Blast the custom email via your SMTP
            send_otp_email(payload.email, otp)

            return {"message": "Signup successful. Verification code sent to email."}

        except Exception as e:
            # Handle cases where Supabase user exists but profile doesn't, etc.
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def verify_otp(payload: VerifyOTPRequest):
        try:
            # 1. Fetch the latest pending OTP for this email
            otp_res = supabase.table("otp_verifications") \
                .select("*") \
                .eq("email", payload.email) \
                .eq("otp_code", payload.otp_code) \
                .eq("status", "pending") \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if not otp_res.data:
                raise HTTPException(status_code=400, detail="Invalid or incorrect verification code.")
                
            otp_record = otp_res.data[0]

            # 2. Check for expiration
            # We strip 'Z' and replace with UTC offset to keep Python's fromisoformat happy
            expires_at = datetime.fromisoformat(otp_record['expires_at'].replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                supabase.table("otp_verifications").update({"status": "expired"}).eq("id", otp_record['id']).execute()
                raise HTTPException(status_code=400, detail="Code has expired. Please request a new one.")

            # 3. Success! Update OTP table and Profile table
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Close the OTP
            supabase.table("otp_verifications").update({
                "status": "verified", 
                "verified_at": now_iso
            }).eq("id", otp_record['id']).execute()
            
            # Verify the User
            supabase.table("profiles").update({"is_verified": True}).eq("id", otp_record['user_id']).execute()

            return {"message": "Email verified successfully. You can now log in."}
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def resend_otp(payload: ResendOTPRequest):
        try:
            # 1. Verify user exists and isn't already verified
            profile_res = supabase.table("profiles").select("*").eq("email", payload.email).execute()
            if not profile_res.data:
                raise HTTPException(status_code=404, detail="User account not found.")
            
            user = profile_res.data[0]
            if user['is_verified']:
                raise HTTPException(status_code=400, detail="Email is already verified.")

            # 2. Expire all old pending codes for this user
            supabase.table("otp_verifications") \
                .update({"status": "expired"}) \
                .eq("email", payload.email) \
                .eq("status", "pending") \
                .execute()

            # 3. Create fresh OTP
            otp = generate_otp()
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            
            supabase.table("otp_verifications").insert({
                "email": payload.email,
                "otp_code": otp,
                "type": "signup",
                "status": "pending",
                "expires_at": expires_at,
                "user_id": user['id']
            }).execute()

            # 4. Send the new email
            send_otp_email(payload.email, otp)

            return {"message": "New verification code sent."}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def login_user(payload: LoginRequest):
        try:
            # 1. Custom check: Is the user verified in our profiles table?
            profile_res = supabase.table("profiles").select("is_verified").eq("email", payload.email).execute()
            
            if not profile_res.data:
                raise HTTPException(status_code=401, detail="User not found.")
                
            if not profile_res.data[0]['is_verified']:
                raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

            # 2. Supabase verifies password & issues the JWT
            auth_res = supabase.auth.sign_in_with_password({
                "email": payload.email,
                "password": payload.password
            })

            return {
                "message": "Login successful.",
                "access_token": auth_res.session.access_token,
                "user_id": auth_res.user.id
            }
        except Exception as e:
            # Catches wrong passwords or Supabase-specific auth errors
            raise HTTPException(status_code=401, detail="Invalid email or password.")