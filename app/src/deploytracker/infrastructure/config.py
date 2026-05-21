from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "deploytracker"
    service_version: str = "0.1.0"
    env: str = "demo"
    database_url: str = "postgresql+psycopg2://deploytracker:deploytracker@localhost:5432/deploytracker"
    otlp_endpoint: str = "http://otel-collector.observability:4317"
    log_level: str = "INFO"
    jwt_secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    admin_username: str = "admin"
    admin_password: str = "change-me"

    model_config = {
        "env_prefix": "DEPLOYTRACKER_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings() -> Settings:
    return Settings()
