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


class BusinessEntityParams(BaseSettings):
    """Landlord information to be listed on the invoice"""

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
