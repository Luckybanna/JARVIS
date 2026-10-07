"""
Local / Self-hosted AI Provider for JARVIS.
Connects to OpenAI-compatible endpoints (e.g. Ollama, LM Studio, vLLM, llama.cpp server).
"""

import json
import time
from typing import Iterator, List, Optional
import httpx

from app.ai.base import AIProvider, AIResponse, ChatMessage, TokenUsage
from app.core.logger import get_logger

logger = get_logger("ai.local")


class LocalProvider(AIProvider):
    """Integration for local or custom OpenAI-compatible HTTP servers."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model_name: str = "llama3.2",
        timeout: float = 60.0,
    ):
        super().__init__(model_name=model_name, timeout=timeout)
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"

    @property
    def provider_name(self) -> str:
        return "local"

    def _build_payload(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> dict:
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            payload_messages.append({"role": msg.role.value, "content": msg.content})

        return {
            "model": self.model_name,
            "messages": payload_messages,
            "temperature": temperature if temperature is not None else 0.7,
            "max_tokens": max_tokens if max_tokens is not None else 1024,
            "stream": stream,
        }

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Sends request to local HTTP endpoint."""
        start_time = time.perf_counter()
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(self.endpoint, json=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                if res.status_code != 200:
                    return AIResponse(
                        content=f"[Local provider HTTP {res.status_code}: {res.text}]",
                        model=self.model_name,
                        latency_ms=latency_ms,
                        error=f"HTTP {res.status_code}",
                    )

                data = res.json()
                content = data["choices"][0]["message"]["content"]
                finish_reason = data["choices"][0].get("finish_reason", "stop")

                usage = TokenUsage()
                if "usage" in data and data["usage"]:
                    u = data["usage"]
                    usage = TokenUsage(
                        prompt_tokens=u.get("prompt_tokens", 0),
                        completion_tokens=u.get("completion_tokens", 0),
                        total_tokens=u.get("total_tokens", 0),
                    )

                return AIResponse(
                    content=content,
                    model=self.model_name,
                    usage=usage,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                    raw_response=data,
                )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Local provider error: {e}")
            return AIResponse(
                content=f"[Error contacting local AI server at {self.base_url}: {e}]",
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
        """Streams tokens from local endpoint using SSE (Server-Sent Events)."""
        payload = self._build_payload(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", self.endpoint, json=payload) as response:
                    for line in response.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Local stream error: {e}")
            yield f"[Local stream error: {e}]"

    def health_check(self) -> tuple[bool, str]:
        """Checks if local endpoint is reachable."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    return True, "Online"
                return False, f"Server responded with HTTP {res.status_code}"
        except Exception as e:
            return False, f"Offline ({e})"
