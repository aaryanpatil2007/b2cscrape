from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://leadflow:leadflow@db:5432/leadflow"
    headless: bool = True

    model_config = {"env_prefix": "LEADFLOW_"}


settings = Settings()
