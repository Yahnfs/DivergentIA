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

    # --- Contas (login/cadastro/recuperação) ---------------------------------------------------
    # Chave usada para assinar o cookie de sessão. Troque por um valor aleatório antes de expor o
    # servidor fora da sua máquina (ex.: python -c "import secrets; print(secrets.token_hex(32))").
    secret_key: str = "troque-esta-chave-antes-de-usar-fora-do-seu-computador"
    access_token_expire_minutes: int = 60 * 24 * 14  # 14 dias
    cookie_secure: bool = False  # True exige HTTPS; deixe False para testar em http://localhost

    # Login com Google ("Entrar com Google"): crie um "ID do cliente OAuth" em
    # https://console.cloud.google.com/apis/credentials (tipo "Aplicativo da Web") e cole aqui.
    # Enquanto estiver vazio, o botão de login com Google some das telas, sem quebrar nada.
    google_client_id: str | None = None

    # Captcha (Google reCAPTCHA v2): registre o site em https://www.google.com/recaptcha/admin
    # e cole as duas chaves abaixo. Enquanto estiverem vazias, o captcha não aparece e a verificação
    # é pulada (útil para testar localmente antes de configurar).
    recaptcha_site_key: str | None = None
    recaptcha_secret_key: str | None = None

    # E-mail (confirmação de cadastro e recuperação de senha): "console" (padrão, grátis) só
    # escreve o link no terminal do servidor — ótimo para testar. "smtp" envia de verdade; configure
    # as variáveis SMTP_* abaixo (ex.: Gmail com uma "senha de app").
    email_provider: str = "console"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_usuario: str | None = None
    smtp_senha: str | None = None
    smtp_remetente: str = "DivergentIA <nao-responda@divergentia.local>"

    # Usado para montar os links enviados por e-mail (ex.: http://localhost:8000).
    app_base_url: str = "http://localhost:8000"

    # Painel de administração: só quem entra com esse usuário/senha pode cadastrar ou verificar locais
    # acessíveis (ver /auth/admin-login). Não é uma conta de usuário comum. Troque a senha padrão antes
    # de expor o servidor fora da sua máquina.
    admin_usuario: str = "admin"
    admin_senha: str = "UniSales2026"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
