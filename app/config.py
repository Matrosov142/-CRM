from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ПОТОК CRM"
    environment: str = "development"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    allow_bootstrap_registration: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    document_storage_path: str = "/var/lib/potok-crm/documents"
    document_max_bytes: int = 26214400
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

settings = Settings()
