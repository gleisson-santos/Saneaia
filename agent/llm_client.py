"""Cliente HTTP para a API OpenRouter (DeepSeek LLM)."""

import httpx
from config.settings import get_settings
from agent.prompts import SYSTEM_PROMPT


class LLMClient:
    """Cliente para interação com o DeepSeek via OpenRouter."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://plataforma-saneamento.com",
            "X-Title": "Plataforma Inteligencia Operacional Saneamento",
        }

    async def chat(
        self,
        user_message: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> str:
        """
        Envia mensagem ao LLM e retorna a resposta.

        Args:
            user_message: Mensagem do usuário/sistema
            system_prompt: Prompt de sistema personalizado
            temperature: Criatividade (0.0 = determinístico, 1.0 = criativo)
            max_tokens: Máximo de tokens na resposta

        Returns:
            Texto da resposta do LLM
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_URL,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # Extrair resposta
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")

        return "Não foi possível gerar uma resposta."

    async def chat_with_history(
        self,
        messages: list[dict],
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> str:
        """
        Chat com histórico de mensagens.

        Args:
            messages: Lista de dict com 'role' e 'content'
            system_prompt: Prompt de sistema
            temperature: Temperatura
            max_tokens: Max tokens

        Returns:
            Resposta do LLM
        """
        all_messages = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
        ] + messages

        payload = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_URL,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")

        return "Não foi possível gerar uma resposta."

    async def ping(self) -> bool:
        """Testa a conexão com a API."""
        try:
            response = await self.chat("Responda apenas: OK", max_tokens=10)
            return "OK" in response.upper() if response else False
        except Exception as e:
            print(f"❌ Erro no ping LLM: {e}")
            return False


def get_llm_client() -> LLMClient:
    """Factory para o cliente LLM."""
    return LLMClient()
