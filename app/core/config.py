from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "DB Designer Backend"
    DATABASE_URL: str
    GEMINI_API_KEY: str = ""
    
    # SMTP Config
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    
    MAIL_HOST: str = ""
    MAIL_PORT: int = 587
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM_ADDRESS: str = ""
    MAIL_FROM_NAME: str = ""
    MAIL_ENCRYPTION: str = ""
    MAIL_MAILER: str = ""
    MAIL_SCHEME: str = ""

    
    # Configuraciones JWT (Para futura implementación de Auth)
    SECRET_KEY: str = "super_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
