from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.slack"), extra="ignore")

    openai_api_key: str = ""
    database_url: str = "postgresql://recallhq:recallhq@localhost:5432/recallhq"
    generation_model: str = "gpt-5.4-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    open_router: str = ""
    rerank_model: str = "typesafe/jev-1.13-20260917"
    rerank_fallback_model: str = "openai/gpt-6-luna-decisions-20261006"
    rerank_top_k: int = 10
    database_write_url: str = ""
    database_migration_url: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
    slack_encryption_key: str = ""
    slack_public_url: str = ""
    slack_user_commands_per_minute: int = 5
    slack_workspace_commands_per_day: int = 200
    slack_history_interval_seconds: int = 60
    slack_history_page_size: int = 15
    slack_job_max_attempts: int = 8
    slack_reconcile_interval_seconds: int = 86400

    @property
    def slack_enabled(self) -> bool:
        return all((self.slack_client_id, self.slack_client_secret,
                    self.slack_signing_secret, self.slack_encryption_key, self.slack_public_url))
