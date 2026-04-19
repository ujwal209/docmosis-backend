from fastapi import APIRouter
from app.models.auth_model import SignupRequest, VerifyOTPRequest, LoginRequest,ResendOTPRequest
from app.controllers.auth_ctrl import AuthController

# THIS IS THE VARIABLE main.py IS LOOKING FOR
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup")
async def signup(payload: SignupRequest):
    return AuthController.signup_user(payload)

@router.post("/verify")
async def verify(payload: VerifyOTPRequest):
    return AuthController.verify_otp(payload)

@router.post("/login")
async def login(payload: LoginRequest):
    return AuthController.login_user(payload)


@router.post("/resend-otp")
async def resend_otp(payload: ResendOTPRequest):
    return AuthController.resend_otp(payload)