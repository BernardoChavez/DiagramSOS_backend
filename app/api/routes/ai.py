import os
import json
import base64
import google.generativeai as genai
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from sqlalchemy.orm import Session
from app.api import deps
from app.models.ai_prompt import AIPromptHistory
from app.models.user import User

router = APIRouter()

# Configurar Gemini API (Se lee de la variable de entorno que seteamos)
genai.configure(api_key=settings.GEMINI_API_KEY)

class AIGenerateRequest(BaseModel):
    prompt: str
    image_base64: Optional[str] = None
    mime_type: Optional[str] = None
    current_schema: Optional[list] = None
    project_id: Optional[int] = None

SYSTEM_PROMPT = """You are an expert database and UML designer assistant.
Your job is to generate ONLY a valid JSON string representing the NEW diagram nodes and edges requested by the user, based on their text or uploaded image sketch.

IMPORTANT RULES:
1. ONLY return the NEW tables and NEW edges the user asks for. Do NOT output the existing tables provided in the schema context unless the user explicitly wants you to modify them.
2. If the user asks to connect to an existing table, use the EXACT id provided in the schema context for the edge source or target.
3. Do not wrap the JSON in markdown blocks (e.g. ```json). Output raw JSON. ALWAYS include both "nodes" and "edges" arrays, even if they are empty.
4. For relations (edges), identify the correct UML relationType based on the user's sketch:
   - "Associate": solid line, no arrows
   - "Compose": solid line with solid diamond
   - "Aggregate": solid line with hollow diamond
   - "Generalize": solid line with hollow triangle (inheritance)
   - "Realize": dashed line with hollow triangle
   - "Dependency": dashed line with open arrow
5. Output format:
{
  "nodes": [
    {
      "id": "new_table_1",
      "type": "tableNode",
      "position": {"x": 100, "y": 100},
      "data": {
        "tableName": "USERS",
        "columns": [
          {"name": "id", "type": "INTEGER", "isPrimary": true, "visibility": "private"}
        ]
      }
    }
  ],
  "edges": [
    {
      "id": "e1-2",
      "source": "existing_id_or_new_table_1",
      "target": "existing_id_or_new_table_2",
      "type": "relationEdge",
      "data": { "relationType": "Compose" }
    }
  ]
}
"""

@router.post("/generate")
def generate_diagram(
    request: AIGenerateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        model = genai.GenerativeModel("gemini-flash-lite-latest")
        
        schema_context = f"\n\nCURRENT EXISTING SCHEMA (Do NOT recreate these tables, but use their exact 'id' if the user asks to relate to them):\n{request.current_schema}\n" if request.current_schema else ""
        full_prompt = SYSTEM_PROMPT + schema_context + "\nUser Request: " + request.prompt

        contents = []
        if request.image_base64 and request.mime_type:
            base64_str = request.image_base64
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            image_data = base64.b64decode(base64_str)
            contents.append({
                "mime_type": request.mime_type,
                "data": image_data
            })
            
        contents.append(full_prompt)

        response = model.generate_content(contents)
        text_response = response.text
        
        # Clean up markdown code blocks if the model ignored instructions
        if text_response.startswith("```"):
            text_response = text_response.strip("`").strip()
            if text_response.lower().startswith("json"):
                text_response = text_response[4:].strip()
        
        text_response = text_response.strip()
        
        parsed = json.loads(text_response)
        if "edges" not in parsed:
            parsed["edges"] = []
        if "nodes" not in parsed:
            parsed["nodes"] = []
        if request.project_id:
            ai_history = AIPromptHistory(
                project_id=request.project_id,
                user_id=current_user.id,
                prompt_text=request.prompt,
                response_json=parsed
            )
            db.add(ai_history)
            db.commit()
            
        return parsed
        
    except Exception as e:
        print(f"Error generating AI diagram: {e}")
        raise HTTPException(status_code=500, detail=str(e))