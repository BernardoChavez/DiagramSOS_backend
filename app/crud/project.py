from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate
from app.models.version import ProjectVersion

def get_projects_by_owner(db: Session, owner_id: int):
    # Get owned projects
    owned = db.query(Project).filter(Project.owner_id == owner_id).all()
    # Get collaborated projects
    from app.models.collaborator import ProjectCollaborator
    collabs = db.query(ProjectCollaborator).filter(ProjectCollaborator.user_id == owner_id).all()
    collab_project_ids = [c.project_id for c in collabs]
    if collab_project_ids:
        collab_projects = db.query(Project).filter(Project.id.in_(collab_project_ids)).all()
        # merge uniquely
        owned_ids = {p.id for p in owned}
        for cp in collab_projects:
            if cp.id not in owned_ids:
                owned.append(cp)
    return owned

def create_project(db: Session, project: ProjectCreate, owner_id: int):
    db_project = Project(
        name=project.name,
        description=project.description,
        canvas_data=project.canvas_data,
        owner_id=owner_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def update_project_canvas(db: Session, project_id: int, canvas_data: dict, owner_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
        
    is_owner = project.owner_id == owner_id
    if not is_owner:
        from app.models.collaborator import ProjectCollaborator
        is_collab = db.query(ProjectCollaborator).filter(
            ProjectCollaborator.project_id == project_id,
            ProjectCollaborator.user_id == owner_id
        ).first()
        if not is_collab:
            return None
            
    project.canvas_data = canvas_data
    
    from app.models.version import ProjectVersion
    last_version = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id).order_by(ProjectVersion.version_number.desc()).first()
    next_v_num = (last_version.version_number + 1) if last_version else 1
    
    new_version = ProjectVersion(
        project_id=project_id,
        version_number=next_v_num,
        commit_message="Guardado de version",
        canvas_data=canvas_data,
        created_by=owner_id
    )
    db.add(new_version)
    
    db.commit()
    db.refresh(project)
    return project

def delete_project(db: Session, project_id: int, owner_id: int):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == owner_id).first()
    if project:
        db.delete(project)
        db.commit()
        return True
    return False
