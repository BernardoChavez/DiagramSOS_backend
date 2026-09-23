from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any
import json

from app.api import deps
from app.models.project import Project
from app.models.collaborator import ProjectCollaborator
from app.core.security import ALGORITHM
from jose import jwt
from app.core.config import settings
from app.crud.user import get_user

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Dictionary mapping project_id to a list of active websocket connections
        # e.g. { 1: [ws1, ws2], 2: [ws3] }
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Dictionary to store user info for each websocket to broadcast who is who
        # { websocket_object: {"user_id": 1, "email": "test@test.com"} }
        self.connection_info: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket, project_id: int, user: dict):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        
        # Check limit of 3 unique users
        unique_users = set()
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                u_info = self.connection_info.get(connection)
                if u_info:
                    unique_users.add(u_info['id'])
                
        if len(unique_users) >= 3 and user['id'] not in unique_users:
            await websocket.send_json({"type": "ERROR", "message": "Sala llena (Límite 3 usuarios)"})
            await websocket.close(code=4003)
            return False
            
        self.active_connections[project_id].append(websocket)
        self.connection_info[websocket] = user
        
        # Send current users to the new user
        existing_users = [
            self.connection_info[ws]
            for ws in self.active_connections[project_id]
            if ws != websocket
        ]
        await websocket.send_json({
            "type": "ROOM_STATE",
            "users": existing_users
        })
        
        # Broadcast that a new user joined
        await self.broadcast(project_id, {
            "type": "USER_JOINED",
            "user": user
        }, exclude=websocket)
        
        return True

    def disconnect(self, websocket: WebSocket, project_id: int):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
                
        user = self.connection_info.get(websocket)
        if user:
            del self.connection_info[websocket]
            # Cannot await broadcast here easily because it's a sync function,
            # but we can return the user to let the caller broadcast it.
        return user

    async def broadcast(self, project_id: int, message: dict, exclude: WebSocket = None):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except:
                        pass

manager = ConnectionManager()

async def get_current_user_ws(token: str, db: Session):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
    except Exception:
        return None
    user = get_user(db, user_id=user_id)
    return user

@router.websocket("/{project_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    project_id: int, 
    token: str = Query(...),
    db: Session = Depends(deps.get_db)
):
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001)
        return

    # Check roles
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        await websocket.close(code=4004)
        return
        
    is_owner = project.owner_id == user.id
    is_collaborator = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == user.id
    ).first()

    if not is_owner and not is_collaborator:
        await websocket.close(code=4003)
        return

    user_info = {"id": user.id, "email": user.email, "role": "owner" if is_owner else is_collaborator.role}
    connected = await manager.connect(websocket, project_id, user_info)
    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Broadcast the message to all other connected clients
                await manager.broadcast(project_id, message, exclude=websocket)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        user_info = manager.disconnect(websocket, project_id)
        if user_info:
            await manager.broadcast(project_id, {
                "type": "USER_LEFT",
                "user": user_info
            })