import json
from uuid import UUID

import loguru
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

logger = loguru.logger


class DBConfigs(BaseSettings):
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class BusinessEntityParams(BaseSettings):
    business_name: str
    business_address_1: str
    business_address_2: str
    business_contact_phone: str
    business_contact_email: str
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    def model_post_init(self, __context):
        self.business_name = self.business_name.replace("_", " ")
        self.business_address_1 = self.business_address_1.replace("_", " ")
        self.business_address_2 = self.business_address_2.replace("_", " ")
        self.business_contact_phone = self.business_contact_phone.replace("_", " ")
        self.business_contact_email = self.business_contact_email.replace("_", " ")


def build_connection_string(cfg: DBConfigs) -> str:
    uri = f"""postgresql://{cfg.db_user}:{cfg.db_password}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}"""
    return uri


def get_logger():
    return logger


def engine_serializer(x):
    if isinstance(x, UUID):
        return str(x)
    elif isinstance(x, dict):
        return json.dumps(x)
    else:
        return x
