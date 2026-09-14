from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "ollama"  # "ollama" ou "claude"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    database_url: str = "sqlite:///./data/locais.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
