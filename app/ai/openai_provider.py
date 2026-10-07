"""
OpenAI AI Provider for JARVIS.
Supports GPT-4o, GPT-4o-mini, and other OpenAI chat completion models.
"""

import time
from typing import Iterator, List, Optional

from app.ai.base import AIProvider, AIResponse, ChatMessage, MessageRole, TokenUsage
from app.core.logger import get_logger

logger = get_logger("ai.openai")


class OpenAIProvider(AIProvider):
    """Integration for OpenAI chat completion models."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        timeout: float = 30.0,
    ):
        super().__init__(model_name=model_name, timeout=timeout)
        self.api_key = api_key.strip() if api_key else ""
        self._client = None
        self._init_client()

    @property
    def provider_name(self) -> str:
        return "openai"

    def _init_client(self) -> None:
        if not self.api_key:
            logger.warning("OpenAIProvider initialized without API key")
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, timeout=self.timeout)
            logger.info(f"OpenAI client initialized with model '{self.model_name}'")
        except Exception as e:
            logger.error(f"Failed to configure OpenAI client: {e}")
            self._client = None

    def _build_payload_messages(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
    ) -> List[dict]:
        payload = []
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload.append({"role": msg.role.value, "content": msg.content})
        return payload

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Synchronously calls OpenAI Chat Completions API."""
        if not self.api_key:
            return AIResponse(
                content="[Configuration Error: OPENAI_API_KEY is missing. Please set it in your .env file.]",
                model=self.model_name,
                error="Missing API key",
            )

        start_time = time.perf_counter()
        try:
            if not self._client:
                self._init_client()

            payload = self._build_payload_messages(messages, system_prompt)

            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=payload,
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=max_tokens if max_tokens is not None else 1024,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"

            usage = TokenUsage()
            if response.usage:
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                    total_tokens=response.usage.total_tokens or 0,
                )

            return AIResponse(
                content=content,
                model=self.model_name,
                usage=usage,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                raw_response=response,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"OpenAI API generation error: {e}", exc_info=True)
            return AIResponse(
                content=f"[Error contacting OpenAI: {str(e)}]",
                model=self.model_name,
                latency_ms=latency_ms,
                error=str(e),
            )

    def stream(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Streams response tokens from OpenAI."""
        if not self.api_key:
            yield "[Error: OPENAI_API_KEY is not configured]"
            return

        try:
            if not self._client:
                self._init_client()

            payload = self._build_payload_messages(messages, system_prompt)

            response_stream = self._client.chat.completions.create(
                model=self.model_name,
                messages=payload,
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=max_tokens if max_tokens is not None else 1024,
                stream=True,
            )

            for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}", exc_info=True)
            yield f"[Streaming error: {e}]"

    def health_check(self) -> tuple[bool, str]:
        """Validates OpenAI API credentials with a minimal ping."""
        if not self.api_key:
            return False, "OPENAI_API_KEY is not configured"
        try:
            test_resp = self.generate(
                messages=[ChatMessage.user("ping")],
                max_tokens=5,
            )
            if test_resp.error:
                return False, test_resp.error
            return True, f"Online (Latency: {test_resp.latency_ms:.1f}ms)"
        except Exception as e:
            return False, str(e)
