from pydantic import BaseModel

class CollaboratorBase(BaseModel):
    role: str

class CollaboratorCreate(CollaboratorBase):
    user_id: int
    project_id: int

class CollaboratorResponse(CollaboratorBase):
    id: int
    project_id: int
    user_id: int

    class Config:
        from_attributes = True
