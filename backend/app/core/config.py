from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Soft Skills AI Platform"
    API_V1_STR: str = "/api/v1"
    
    # Database - Individual components (for backward compatibility)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "softskills_db"
    POSTGRES_PORT: str = "5432"
    
    # Database URL - Can be set directly or constructed from components
    # Priority: DATABASE_URL from env > constructed from components
    DATABASE_URL: Optional[str] = None

    # JWT
    SECRET_KEY: str = "YOUR_SUPER_SECRET_KEY_CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Yandex Cloud
    YANDEX_FOLDER_ID: str = ""
    YANDEX_API_KEY: str = ""

    DEFAULT_ADMIN_EMAIL: str = "admin123@admin123.com"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    # Development plan generation
    MIN_ANALYSES_FOR_PLAN: int = 3

    class Config:
        env_file = ".env"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # If DATABASE_URL is not set, construct it from components
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        if self.DEFAULT_ADMIN_EMAIL and "@" in self.DEFAULT_ADMIN_EMAIL:
            local_part, domain = self.DEFAULT_ADMIN_EMAIL.split("@", 1)
            if domain.lower().endswith(".local"):
                self.DEFAULT_ADMIN_EMAIL = f"{local_part}@admin123.com"

settings = Settings()
