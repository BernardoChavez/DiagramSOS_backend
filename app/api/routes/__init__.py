from fastapi import APIRouter
from app.api.routes import auth, projects, generator, ai, collaboration, interop

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(generator.router, prefix="/generator", tags=["generator"])
router.include_router(ai.router, prefix="/ai", tags=["ai"])

router.include_router(collaboration.router, prefix="/collaboration", tags=["collaboration"])
router.include_router(interop.router, prefix="/projects", tags=["interop"])
