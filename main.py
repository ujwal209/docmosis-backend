from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import your routers
from app.routes.auth_route import router as auth_router
from app.routes.user_route import router as user_router  # NEW IMPORT

app = FastAPI(
    title="Docmosiss Engine API",
    description="Vercel Serverless Backend for Document Conversion",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the routers
app.include_router(auth_router)
app.include_router(user_router)  # ADD THIS LINE

@app.get("/")
async def root():
    return {"message": "Docmosiss API is operational. Powered by FastAPI & Supabase."}