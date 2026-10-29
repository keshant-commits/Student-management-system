from fastapi import FastAPI
from app.core.config import Settings, load_settings

settings = load_settings()

app = FastAPI(
    title="Student Management System",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
