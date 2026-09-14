from abc import ABC, abstractmethod

import httpx

from app.config import settings


class LLMProviderError(Exception):
    """Erro ao chamar o provedor de LLM configurado."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Envia o prompt ao modelo e retorna o texto de resposta."""


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=120,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                "Não foi possível conectar ao Ollama. Verifique se ele está rodando "
                f"em {self.base_url} (comando: 'ollama serve') e se o modelo "
                f"'{self.model}' foi baixado (comando: 'ollama pull {self.model}')."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"Erro do Ollama: {exc.response.text}") from exc

        data = response.json()
        return data["message"]["content"]


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - repassa qualquer erro da API como erro de provedor
            raise LLMProviderError(f"Erro ao chamar a Claude API: {exc}") from exc

        textos = [bloco.text for bloco in response.content if bloco.type == "text"]
        return "\n".join(textos)


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "claude":
        if not settings.anthropic_api_key:
            raise LLMProviderError(
                "LLM_PROVIDER está definido como 'claude', mas ANTHROPIC_API_KEY não foi configurada no .env."
            )
        return ClaudeProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
