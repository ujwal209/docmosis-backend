from pydantic import BaseModel
from typing import Optional

class OnboardingRequest(BaseModel):
    user_type: str
    primary_use_case: str
    bio: Optional[str] = None