from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://leadflow:leadflow@db:5432/leadflow"
    headless: bool = True

    # Hunter.io
    hunter_api_key: str = ""

    # SMTP for outreach emails
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "LeadFlow"

    model_config = {"env_prefix": "LEADFLOW_"}


settings = Settings()
