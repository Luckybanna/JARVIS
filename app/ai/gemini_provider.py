"""
Google Gemini AI Provider for JARVIS.
Supports Gemini 2.5 Flash, 1.5 Flash, and other Gemini models.
"""

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import time
from typing import Iterator, List, Optional

from app.ai.base import AIProvider, AIResponse, ChatMessage, MessageRole, TokenUsage
from app.core.logger import get_logger

logger = get_logger("ai.gemini")


class GeminiProvider(AIProvider):
    """Integration for Google Gemini models."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.8-flash",
        timeout: float = 30.0,
    ):
        super().__init__(model_name=model_name, timeout=timeout)
        self.api_key = api_key.strip() if api_key else ""
        self._client = None
        self._init_client()

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _init_client(self) -> None:
        if not self.api_key:
            logger.warning("GeminiProvider initialized without API key")
            return
        try:
            try:
                import truststore
                truststore.inject_into_ssl()
            except Exception:
                pass
            import google.generativeai as genai
            genai.configure(api_key=self.api_key, transport="rest")
            self._client = genai
            logger.info(f"Gemini client initialized with model '{self.model_name}' (transport=rest)")
        except Exception as e:
            logger.error(f"Failed to configure Gemini client: {e}")
            self._client = None

    def _format_contents(self, messages: List[ChatMessage]) -> List[dict]:
        """Convert standard ChatMessage objects into Gemini's contents format."""
        contents = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System prompt is handled separately via system_instruction
                continue
            role = "user" if msg.role == MessageRole.USER else "model"
            contents.append({"role": role, "parts": [msg.content]})
        return contents

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Synchronously calls Gemini API and returns an AIResponse."""
        if not self.api_key:
            return AIResponse(
                content="[Configuration Error: GEMINI_API_KEY is missing. Please set it in your .env file.]",
                model=self.model_name,
                error="Missing API key",
            )

        start_time = time.perf_counter()
        try:
            if not self._client:
                self._init_client()

            genai = self._client
            config = genai.GenerationConfig(
                temperature=temperature if temperature is not None else 0.7,
                max_output_tokens=max_tokens if max_tokens is not None else 1024,
            )

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt if system_prompt else None,
                generation_config=config,
            )

            contents = self._format_contents(messages)
            if not contents:
                return AIResponse(
                    content="",
                    model=self.model_name,
                    error="No user/assistant messages provided",
                )

            # Generate content
            response = model.generate_content(contents)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            content_text = ""
            if response and hasattr(response, "text"):
                try:
                    content_text = response.text
                except Exception:
                    # In case of safety blocks or multiple candidates
                    if response.candidates and response.candidates[0].content.parts:
                        content_text = "".join(
                            part.text for part in response.candidates[0].content.parts if hasattr(part, "text")
                        )

            # Extract token usage if available
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
                completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

            return AIResponse(
                content=content_text,
                model=self.model_name,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                latency_ms=latency_ms,
                raw_response=response,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Gemini API generation error: {e}", exc_info=True)
            return AIResponse(
                content=f"[Error contacting Gemini: {str(e)}]",
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
        """Streams response tokens from Gemini."""
        if not self.api_key:
            yield "[Error: GEMINI_API_KEY is not configured]"
            return

        try:
            if not self._client:
                self._init_client()

            genai = self._client
            config = genai.GenerationConfig(
                temperature=temperature if temperature is not None else 0.7,
                max_output_tokens=max_tokens if max_tokens is not None else 1024,
            )

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt if system_prompt else None,
                generation_config=config,
            )

            contents = self._format_contents(messages)
            response = model.generate_content(contents, stream=True)

            for chunk in response:
                if hasattr(chunk, "text") and chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}", exc_info=True)
            yield f"[Streaming error: {e}]"

    def health_check(self) -> tuple[bool, str]:
        """Validates API credentials with a minimal ping."""
        if not self.api_key:
            return False, "GEMINI_API_KEY is not configured"
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
