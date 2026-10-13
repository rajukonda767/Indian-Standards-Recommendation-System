"""
config.py
=========
Global configuration and environment settings for the FastAPI backend.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory: standards/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables
env_paths = [
    BASE_DIR / "backend" / ".env",
    BASE_DIR / ".env"
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break

class Settings:
    PROJECT_NAME: str = "SIH-26108 BIS AI Procurement Copilot"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    if DATABASE_URL and "sslmode" not in DATABASE_URL:
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

    # Groq Cloud
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_KEY_2: str = os.getenv("GROQ_API_KEY_2", "")
    GROQ_API_KEY_3: str = os.getenv("GROQ_API_KEY_3", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

    @property
    def GROQ_API_KEYS(self) -> list[str]:
        keys = []
        for k in [self.GROQ_API_KEY, self.GROQ_API_KEY_2, self.GROQ_API_KEY_3]:
            k_val = k.strip() if k else ""
            if k_val and k_val not in keys:
                keys.append(k_val)
        return keys

    # Local GPU Embedding
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024

    # Scoring & Gate Thresholds
    BOUNDARY_THRESHOLD: float = 0.45
    AMBIGUITY_THRESHOLD: float = 0.05

settings = Settings()
