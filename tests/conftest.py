import os

# Ensure Settings can load before any app imports during collection.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/safetour",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["AUTO_CREATE_TABLES"] = "false"
