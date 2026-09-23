from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List
from app.generator import generate_project_zip

router = APIRouter()

class DiagramData(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

@router.post("/generate-springboot")
async def generate_springboot(diagram: dict):
    # Pass the raw diagram dict to the generator
    zip_buffer = generate_project_zip(diagram)
    
    headers = {
        'Content-Disposition': 'attachment; filename="springboot-api.zip"'
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
