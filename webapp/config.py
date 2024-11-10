from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class AppConfig(BaseSettings):
    """For internal usage"""

    host: str = "http://billing_service"
    port: int = 8001
    template_path: str = "template/bill_template.xlsx"
    output_path: str = "invoices/"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
