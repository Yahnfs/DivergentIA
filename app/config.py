from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "ollama"  # "ollama" ou "claude"

    ollama_base_url: str = "http://localhost:11434"
    # llama3.2:3b: cabe 100% na GPU de 6 GB (a 8B ocupa CPU e passa de 20s/turno); o modelo só escreve uma frase
    # curta (o resto da resposta é montado pelo servidor a partir da base verificada), então um modelo pequeno basta.
    ollama_model: str = "llama3.2:3b"
    ollama_keep_alive: str = "30m"  # por quanto tempo o modelo fica carregado na memória após o último uso
    ollama_num_ctx: int = 4096      # janela de contexto (o padrão do Ollama pode cortar o início do prompt)
    ollama_num_predict: int = 1400  # limite de tokens da resposta

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    database_url: str = "sqlite:///./data/locais.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
