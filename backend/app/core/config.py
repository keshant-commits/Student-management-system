import os


class Settings:
    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development")
        self.secret_key = os.getenv("SECRET_KEY")
        if not self.secret_key:
            raise RuntimeError("Missing required environment variable: SECRET_KEY")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./dev.db")


def get_settings() -> Settings:
    return Settings()


settings = None


def load_settings() -> Settings:
    global settings
    settings = Settings()
    return settings
