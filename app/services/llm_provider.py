import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

log = logging.getLogger("divergentia.llm")


class LLMProviderError(Exception):
    """Erro ao chamar o provedor de LLM configurado."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict], schema: dict | None = None) -> str:
        """Envia a conversa ao modelo e devolve o texto da resposta.

        messages: lista de {"role": "user" | "assistant", "content": str}, terminando numa mensagem do usuário.
        schema: JSON Schema que a resposta deve seguir (o Ollama força o formato; no Claude vai no prompt).
        """


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, keep_alive: str, num_ctx: int, num_predict: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.keep_alive = keep_alive
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def generate(self, system_prompt: str, messages: list[dict], schema: dict | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0.2, "num_ctx": self.num_ctx, "num_predict": self.num_predict},
        }
        if schema:
            payload["format"] = schema  # "structured outputs": a resposta sai sempre no formato do esquema
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=240)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                "Não foi possível conectar ao Ollama. Verifique se ele está rodando "
                f"em {self.base_url} (comando: 'ollama serve') e se o modelo "
                f"'{self.model}' foi baixado (comando: 'ollama pull {self.model}')."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError("O modelo demorou demais para responder. Tente de novo em instantes.") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(f"Erro do Ollama: {exc.response.text}") from exc

        data = response.json()
        usados = data.get("prompt_eval_count", 0)
        if usados >= self.num_ctx - 64:
            # O Ollama descarta o começo do prompt quando ele passa da janela: as regras somem sem aviso.
            log.warning("Prompt com %s tokens em uma janela de %s: as regras podem ter sido cortadas.", usados, self.num_ctx)
        else:
            log.info("Prompt: %s tokens (janela de %s); resposta: %s tokens", usados, self.num_ctx, data.get("eval_count", 0))
        return data["message"]["content"]


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, messages: list[dict], schema: dict | None = None) -> str:
        system = system_prompt
        if schema:
            system += (
                "\n\nResponda SOMENTE com um objeto JSON válido que siga exatamente este JSON Schema, "
                "sem nenhum texto antes ou depois:\n" + json.dumps(schema, ensure_ascii=False)
            )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
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

    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=settings.ollama_num_ctx,
        num_predict=settings.ollama_num_predict,
    )


def aquecer_modelo() -> None:
    """Carrega o modelo do Ollama na memória, para a 1ª pergunta não pagar o tempo de carga."""
    if settings.llm_provider != "ollama":
        return
    try:
        # Sem prompt, o /api/generate apenas carrega o modelo (e respeita o keep_alive e a janela de contexto).
        httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "keep_alive": settings.ollama_keep_alive,
                "options": {"num_ctx": settings.ollama_num_ctx},
            },
            timeout=300,
        )
    except httpx.HTTPError:
        pass  # Ollama fora do ar: o erro, com orientação, aparece na primeira pergunta
