"""Configuration management"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration"""

    # Server settings
    TOKEN_SECRET_KEY: str = os.getenv("TOKEN_SECRET_KEY", "change-me-in-production")
    SERVER_URL: str = os.getenv("SERVER_URL", "http://localhost:8000")
    AUTH_ISSUER_URL: str = os.getenv("AUTH_ISSUER_URL", "https://auth.example.com")

    # Langfuse settings
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Token registry file
    TOKENS_FILE: Path = Path(os.getenv("TOKENS_FILE", "tokens.json"))

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if cls.TOKEN_SECRET_KEY == "change-me-in-production":
            print("Warning: Using default TOKEN_SECRET_KEY, change it in production!")

        if not cls.LANGFUSE_PUBLIC_KEY or not cls.LANGFUSE_SECRET_KEY:
            print("Warning: Langfuse credentials not configured")
            return False

        return True


config = Config()
