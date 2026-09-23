from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    canvas_data: Dict[str, Any] = {}

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    canvas_data: Optional[Dict[str, Any]] = None

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
