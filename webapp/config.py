from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class AppConfig(BaseSettings):
    host: str
    port: int
    template_path: str
    output_path: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
