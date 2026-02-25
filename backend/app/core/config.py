from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Soft Skills AI Platform"
    API_V1_STR: str = "/api/v1"

    # Database components (used when DATABASE_URL is not provided)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "softskills_db"
    POSTGRES_PORT: str = "5432"

    # Database URL (can be Render/Railway style postgres:// URL)
    DATABASE_URL: Optional[str] = None
    DATABASE_SSL: Optional[bool] = None
    DB_CONNECT_TIMEOUT_SECONDS: int = 15
    DB_POOL_PRE_PING: bool = True
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_ECHO_SQL: bool = False
    DB_STARTUP_MAX_RETRIES: int = 10
    DB_STARTUP_RETRY_DELAY_SECONDS: float = 2.0

    # App startup behavior
    CREATE_TABLES_ON_STARTUP: bool = True

    # CORS
    CORS_ORIGINS: str = ""
    CORS_ALLOW_ALL: bool = False

    # JWT
    SECRET_KEY: str = "YOUR_SUPER_SECRET_KEY_CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Yandex Cloud (optional)
    YANDEX_FOLDER_ID: str = ""
    YANDEX_API_KEY: str = ""

    DEFAULT_ADMIN_EMAIL: str = "admin123@admin123.com"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    # Development plan generation
    MIN_ANALYSES_FOR_PLAN: int = 3

    class Config:
        env_file = ".env"

    @staticmethod
    def _to_asyncpg_scheme(raw_url: str) -> str:
        value = raw_url.strip()
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql+psycopg2://"):
            value = "postgresql+asyncpg://" + value[len("postgresql+psycopg2://") :]
        elif value.startswith("postgresql+pg8000://"):
            value = "postgresql+asyncpg://" + value[len("postgresql+pg8000://") :]
        elif value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    @staticmethod
    def _str_to_bool(value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "require", "required"}:
            return True
        if normalized in {"0", "false", "no", "off", "disable", "disabled"}:
            return False
        return None

    def _normalize_database_url(self, raw_url: str) -> tuple[str, Optional[bool]]:
        value = self._to_asyncpg_scheme(raw_url)
        parsed = urlsplit(value)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))

        inferred_ssl: Optional[bool] = None
        sslmode = query.pop("sslmode", None)
        ssl = query.pop("ssl", None)
        if sslmode is not None:
            inferred_ssl = self._str_to_bool(sslmode)
            if inferred_ssl is None:
                inferred_ssl = str(sslmode).strip().lower() not in {"disable", "allow", "prefer"}
        elif ssl is not None:
            inferred_ssl = self._str_to_bool(ssl)

        normalized_url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(query),
                parsed.fragment,
            )
        )
        return normalized_url, inferred_ssl

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        normalized_url, inferred_ssl = self._normalize_database_url(self.DATABASE_URL)
        self.DATABASE_URL = normalized_url
        if self.DATABASE_SSL is None:
            self.DATABASE_SSL = inferred_ssl

        if self.DEFAULT_ADMIN_EMAIL and "@" in self.DEFAULT_ADMIN_EMAIL:
            local_part, domain = self.DEFAULT_ADMIN_EMAIL.split("@", 1)
            if domain.lower().endswith(".local"):
                self.DEFAULT_ADMIN_EMAIL = f"{local_part}@admin123.com"


settings = Settings()
