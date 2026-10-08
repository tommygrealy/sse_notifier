"""Configuration loaded from environment variables (optionally a local .env)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    host: str = "127.0.0.1"
    port: int = 8021
    heartbeat_seconds: float = 15.0
    queue_size: int = 16


def load_settings() -> Settings:
    """Build Settings from the environment. NOTIFY_API_KEY is mandatory."""
    load_dotenv()
    api_key = os.environ.get("NOTIFY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("NOTIFY_API_KEY environment variable is required")
    return Settings(
        api_key=api_key,
        host=os.environ.get("SSE_HOST", "127.0.0.1"),
        port=int(os.environ.get("SSE_PORT", "8021")),
        heartbeat_seconds=float(os.environ.get("SSE_HEARTBEAT_SECONDS", "15")),
    )
