from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    database_url: str = "postgresql://recallhq:recallhq@localhost:5432/recallhq"
    generation_model: str = "gpt-5.4-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    open_router: str = ""
    rerank_model: str = "typesafe/jev-1.13-20260917"
    rerank_fallback_model: str = "openai/gpt-6-luna-decisions-20261006"
    rerank_top_k: int = 10
