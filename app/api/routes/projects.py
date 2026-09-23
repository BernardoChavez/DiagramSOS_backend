
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import project as crud_project
from app.schemas.project import ProjectCreate, ProjectResponse
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
def read_projects(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    projects = crud_project.get_projects_by_owner(db, owner_id=current_user.id)
    return projects

@router.post("/", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    project = crud_project.create_project(db, project=project_in, owner_id=current_user.id)
    return project

@router.put("/{project_id}/canvas", response_model=ProjectResponse)
def update_project_canvas(
    project_id: int,
    canvas_data: dict,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    project = crud_project.update_project_canvas(
        db, project_id=project_id, canvas_data=canvas_data, owner_id=current_user.id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    success = crud_project.delete_project(db, project_id=project_id, owner_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}

from pydantic import BaseModel
class InviteRequest(BaseModel):
    email: str

@router.post("/{project_id}/invite")
def invite_collaborator(
    project_id: int,
    request: InviteRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    # 1. Verify project exists and current_user is owner
    project = crud_project.get_projects_by_owner(db, owner_id=current_user.id)
    project = next((p for p in project if p.id == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owner")
        
    # 2. Find user by email
    from app.crud.user import get_user_by_email
    invitee = get_user_by_email(db, email=request.email)
    if not invitee:
        raise HTTPException(status_code=404, detail="Usuario con este email no encontrado")
        
    # 3. Check if already collaborator
    from app.models.collaborator import ProjectCollaborator
    existing = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == invitee.id
    ).first()
    
    if existing:
        return {"message": "El usuario ya es colaborador"}
        
    # 4. Create collaboration
    collab = ProjectCollaborator(
        project_id=project_id,
        user_id=invitee.id,
        role="editor"
    )
    db.add(collab)
    db.commit()
    

    link = f"http://localhost:5173/editor/{project_id}"
    try:
        host = settings.MAIL_HOST or host
        user = settings.MAIL_USERNAME or user
        pwd = settings.MAIL_PASSWORD or pwd
        port = settings.MAIL_PORT or port
        if host and user:
            msg = MIMEMultipart()
            msg['From'] = user
            msg['To'] = request.email
            msg['Subject'] = f"Invitación para colaborar en el proyecto: {project.name}"
            
            # HTML Email Template
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 40px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-top: 5px solid #2563eb; }}
                    .logo {{ font-size: 28px; font-weight: bold; color: #0f172a; margin-bottom: 24px; text-align: center; letter-spacing: -0.5px; }}
                    .logo span {{ color: #2563eb; }}
                    h1 {{ color: #1e293b; font-size: 22px; text-align: center; margin-bottom: 30px; font-weight: 600; }}
                    p {{ color: #475569; font-size: 16px; line-height: 1.6; margin-bottom: 24px; text-align: center; }}
                    .btn-container {{ text-align: center; margin: 35px 0; }}
                    .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; transition: background-color 0.2s; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3); }}
                    .btn:hover {{ background-color: #1d4ed8; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.4); }}
                    .footer {{ text-align: center; color: #94a3b8; font-size: 14px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; }}
                    .project-name {{ font-weight: 700; color: #0f172a; background-color: #f1f5f9; padding: 2px 8px; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">Diagram<span>SoS</span></div>
                    <h1>¡Has sido invitado a colaborar!</h1>
                    <p>Hola,</p>
                    <p>Un miembro de nuestro equipo te ha invitado a colaborar en tiempo real en el proyecto <br><br><span class="project-name">{project.name}</span></p>
                    
                    <div class="btn-container">
                        <a href="{link}" class="btn">Abrir Proyecto</a>
                    </div>
                    
                    <p style="font-size: 14px;">Si el botón superior no funciona, también puedes copiar y pegar este enlace en tu navegador:</p>
                    <p style="word-break: break-all; color: #2563eb; font-size: 13px;">{link}</p>
                    
                    <div class="footer">
                        <p>© 2026 Equipo de DiagramSoS.<br>Todos los derechos reservados.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html, 'html'))
            
            server = smtplib.SMTP(host, port)
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
            server.quit()
            print(f"Correo real enviado a {request.email}")
        else:
            print("Variables SMTP no configuradas. Simulando envío.")
            print(f"Enlace de proyecto: {link}")
    except Exception as e:
        print(f"Error enviando correo SMTP: {e}")
        # Seguimos adelante, no rompemos la API

    
    return {"message": "Invitación enviada con éxito"}
