"""Configuration for the MAKER Framework BI Agent Demo."""

import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class AgentConfig(BaseModel):
    """Configuration for the agent pipeline."""

    google_api_key: str = Field(..., description="Google API key for Gemini models")
    db_path: str = Field(default="demo_data/demo.db", description="SQLite database path")
    worker_batch_size: int = Field(default=5, ge=2, description="Workers per voting batch")
    worker_temperatures: list[float] = Field(
        default=[0.0, 0.2, 0.3, 0.4, 0.5],
        description="Per-worker temperatures (graduated Config C)",
    )
    max_retry_batches: int = Field(default=5, ge=1, description="Max voting batches before safety valve")
    query_timeout_seconds: int = Field(default=30, ge=5, description="SQL query timeout")

    @classmethod
    def from_env(cls) -> "AgentConfig":
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        return cls(
            google_api_key=api_key,
            db_path=os.getenv("DB_PATH", "demo_data/demo.db"),
            worker_batch_size=int(os.getenv("WORKER_BATCH_SIZE", "5")),
            max_retry_batches=int(os.getenv("MAX_RETRY_BATCHES", "5")),
            query_timeout_seconds=int(os.getenv("QUERY_TIMEOUT_SECONDS", "30")),
        )
