from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Ilova sozlamalari — barchasi .env fayldan o'qiladi."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Umumiy ---
    ENV: Literal["dev", "prod", "test"] = "dev"
    PROJECT_NAME: str = "SOC/DLP Monitoring Platform"
    API_V1_PREFIX: str = "/api"

    # --- Database ---
    # Namuna: postgresql+asyncpg://soc:soc@db:5432/soc_platform
    DATABASE_URL: str

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Refresh token cookie ---
    REFRESH_COOKIE_NAME: str = "sd_refresh_token"
    COOKIE_SECURE: bool = False          # prod'da True (HTTPS majburiy)
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    COOKIE_PATH: str = "/api/auth"

    # --- Login attempt limit ---
    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # --- Parol siyosati ---
    PASSWORD_MIN_LENGTH: int = 10

    # --- Xavfsizlik header'lari / HSTS ---
    SECURITY_HEADERS_ENABLED: bool = True
    HSTS_MAX_AGE: int = 63072000  # 2 yil (faqat prod + HTTPS'da yuboriladi)

    # --- Fon tozalash (retention) ---
    CLEANUP_INTERVAL_HOURS: int = 24
    REFRESH_TOKEN_RETENTION_DAYS: int = 7  # bekor qilingan tokenlar shu muddatdan keyin o'chadi
    AUDIT_RETENTION_DAYS: int = 180        # 0 = cheksiz saqlash

    # --- Eksport (jadval yuklab olish) ---
    EXPORT_DIR: str = "/app/exports"          # tayyor fayllar shu yerga yoziladi
    EXPORT_JOB_MAX_CONCURRENT: int = 3        # bir vaqtda ishlaydigan job cheklovi -> 429
    EXPORT_MAX_ROWS: int = 100_000            # bitta eksportda maksimal qator
    EXPORT_SHARE_TTL_HOURS: int = 48          # ulashish havolasi amal muddati
    EXPORT_KEEP_DAYS: int = 7                 # tayyor eksport fayllari shu muddatdan keyin o'chadi

    # --- Super admin seed ---
    SUPERADMIN_USERNAME: str = "superadmin"
    SUPERADMIN_PASSWORD: str = "ChangeMe123!"

    # --- CORS ---
    # NoDecode: pydantic-settings env qiymatini JSON deb o'qishga urinmasin,
    # o'rniga quyidagi validator vergul bilan ajratadi.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
