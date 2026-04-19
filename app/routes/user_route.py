from fastapi import APIRouter, Depends
from app.models.user_model import OnboardingRequest
from app.controllers.user_ctrl import UserController
from app.core.security import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

# Notice the Depends(get_current_user) - this locks the endpoint down!
@router.post("/onboarding")
async def onboarding(
    payload: OnboardingRequest, 
    user_id: str = Depends(get_current_user)
):
    return UserController.complete_onboarding(user_id, payload)