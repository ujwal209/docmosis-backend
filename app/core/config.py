import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
    SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")
    
    SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))

    # CLOUDINARY
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    
    ILOVEPDF_PUBLIC_KEY = os.environ.get("ILOVEPDF_PUBLIC_KEY")
    ILOVEPDF_SECRET_KEY = os.environ.get("ILOVEPDF_SECRET_KEY")
    
    GROQ_API_KEYS = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]
    TAVILY_API_KEYS = [k.strip() for k in os.environ.get("TAVILY_API_KEYS", "").split(",") if k.strip()]
    GEMINI_API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]

settings = Settings()

# Initialize Cloudinary globally
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)