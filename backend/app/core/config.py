from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = Field(default="HackRTC")
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=True)

    jwt_secret: str = Field(default="change_me_in_prod")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60 * 24)

    database_url: str = Field(default="postgresql+psycopg://app:app@db:5432/app")

    # Optional external IP for TURN, comes from env var TURN_EXTERNAL_IP
    turn_external_ip: str | None = Field(default=None)

    # S3 storage
    s3_endpoint: str | None = Field(default=None, alias="S3_ENDPOINT")
    s3_region: str | None = Field(default=None, alias="S3_REGION")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_access_key: str | None = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: str | None = Field(default=None, alias="S3_SECRET_KEY")
    s3_force_path_style: bool = Field(default=True, alias="S3_FORCE_PATH_STYLE")

    # Recorder config
    ws_base_url: str = Field(default="ws://localhost:8000", alias="WS_BASE_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
