from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any

class AIPromptBase(BaseModel):
    prompt_text: str
    response_json: Dict[str, Any]

class AIPromptCreate(AIPromptBase):
    project_id: int
    user_id: int

class AIPromptResponse(AIPromptBase):
    id: int
    project_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
