from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class VersionBase(BaseModel):
    version_number: int
    commit_message: Optional[str] = None
    canvas_data: Dict[str, Any]

class VersionCreate(VersionBase):
    project_id: int
    created_by: int

class VersionResponse(VersionBase):
    id: int
    project_id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True
