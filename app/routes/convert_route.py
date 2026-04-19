from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.controllers.convert_ctrl import ConvertController
from app.models.convert_model import ConversionRequest

router = APIRouter(prefix="/convert", tags=["Conversions"])

@router.post("/")
async def convert_documents(payload: ConversionRequest, user_id: str = Depends(get_current_user)):
    return ConvertController.process_conversion(user_id, payload)