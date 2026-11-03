import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AeroVoice AI"
    APP_DESCRIPTION: str = "Web-Based Conversational Voice Agent for the Aviation Industry"
    VERSION: str = "1.0.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    CONFIDENCE_THRESHOLD: float = 0.85

    # Optional external credentials (falls back to high-fidelity mock engines)
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
