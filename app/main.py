from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router as api_router

from app.database.session import engine
from app.database.base import Base
import app.models # Para que SQLAlchemy registre las tablas

# Generar las tablas de la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend para Sistema Colaborativo de Diseño de Bases de Datos",
    version="1.0.0",
)

# Configurar CORS (Permitir que el frontend React se conecte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite solicitudes desde cualquier dominio (Vercel)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "API is running correctly"}
