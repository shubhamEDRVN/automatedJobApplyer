"""
Multi-Provider LLM Router with automatic failover.

Supports:
  - Multiple Gemini API keys (each key gets its own free quota)
  - Groq (free tier: 30 RPM, 14400 RPD — very generous)
  - OpenRouter (free models available)

Round-robins through all configured providers.
On rate-limit (429), automatically switches to the next provider.
"""

import os
import json
import time
import asyncio
import httpx
import logging
from typing import Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    """Represents a single AI provider + model combination."""
    name: str
    api_key: str
    model: str
    base_url: str
    is_gemini: bool = False
    failures: int = 0
    last_failure: float = 0.0


class LLMRouter:
    """
    Multi-provider AI router with automatic failover and round-robin.

    Usage:
        router = get_llm_router()
        result = await router.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello!",
            json_mode=False
        )
    """

    def __init__(self):
        self.providers: List[LLMProvider] = []
        self._current_index = 0
        self._load_providers()

    def _load_providers(self):
        """Load all available AI providers from environment variables."""

        # ── 1. Gemini keys (GEMINI_API_KEY, GEMINI_API_KEY_2, ... up to 5) ──
        gemini_models = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
        ]
        for i in range(1, 6):
            key_name = "GEMINI_API_KEY" if i == 1 else f"GEMINI_API_KEY_{i}"
            key = os.environ.get(key_name)
            if key:
                for model in gemini_models:
                    self.providers.append(LLMProvider(
                        name=f"Gemini/{model} [{key_name}]",
                        api_key=key,
                        model=model,
                        base_url="https://generativelanguage.googleapis.com/v1beta",
                        is_gemini=True,
                    ))

        # ── 2. Groq (free: ~30 RPM, ~14 400 RPD) ──
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            groq_models = [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
            ]
            for model in groq_models:
                self.providers.append(LLMProvider(
                    name=f"Groq/{model}",
                    api_key=groq_key,
                    model=model,
                    base_url="https://api.groq.com/openai/v1",
                ))

        # ── 3. OpenRouter (free models available) ──
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            or_models = [
                "google/gemini-2.0-flash-exp:free",
                "meta-llama/llama-3.3-70b-instruct:free",
            ]
            for model in or_models:
                self.providers.append(LLMProvider(
                    name=f"OpenRouter/{model}",
                    api_key=openrouter_key,
                    model=model,
                    base_url="https://openrouter.ai/api/v1",
                ))

        # ── Summary ──
        if not self.providers:
            logger.error("⚠ No AI providers configured! Add at least GEMINI_API_KEY to .env")
        else:
            unique = []
            seen = set()
            for p in self.providers:
                short = p.name.split("[")[0].strip()
                if short not in seen:
                    seen.add(short)
                    unique.append(short)
            logger.info(f"LLM Router ready — {len(self.providers)} slots across {len(unique)} models:")
            for u in unique:
                logger.info(f"  ✓ {u}")

    # ─── Provider selection ───────────────────────────────────────────

    def _get_next_provider(self) -> Optional[LLMProvider]:
        """Round-robin selection, skipping providers on cooldown."""
        if not self.providers:
            return None

        now = time.time()
        tried = 0

        while tried < len(self.providers):
            provider = self.providers[self._current_index]
            self._current_index = (self._current_index + 1) % len(self.providers)
            tried += 1

            # Cooldown: failures × 30 s (max 5 min)
            cooldown = min(provider.failures * 30, 300)
            if provider.failures > 0 and (now - provider.last_failure) < cooldown:
                continue

            return provider

        # Everything on cooldown → pick the one whose cooldown ended earliest
        return min(self.providers, key=lambda p: p.last_failure)

    # ─── Gemini SDK call ──────────────────────────────────────────────

    async def _call_gemini(self, provider: LLMProvider, system_prompt: str,
                           user_prompt: str, json_mode: bool) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=provider.api_key)

        config_kwargs = {
            "system_instruction": system_prompt,
            "temperature": 0.1 if json_mode else 0.7,
        }
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_kwargs)

        response = client.models.generate_content(
            model=provider.model,
            contents=user_prompt,
            config=config,
        )
        return response.text.strip()

    # ─── OpenAI-compatible call (Groq / OpenRouter) ───────────────────

    async def _call_openai_compatible(self, provider: LLMProvider, system_prompt: str,
                                       user_prompt: str, json_mode: bool) -> str:
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        if "openrouter" in provider.base_url:
            headers["HTTP-Referer"] = "https://github.com/automated-internship"
            headers["X-Title"] = "Automated Job Platform"

        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1 if json_mode else 0.7,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{provider.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    # ─── Public interface ─────────────────────────────────────────────

    async def generate(self, system_prompt: str, user_prompt: str,
                       json_mode: bool = False) -> str:
        """
        Generate a response, rotating through providers on failure.

        Args:
            system_prompt: The system instruction.
            user_prompt:   The user query / content.
            json_mode:     If True, requests structured JSON output.

        Returns:
            The model's text response.

        Raises:
            RuntimeError if every provider is exhausted.
        """
        errors: List[str] = []

        # Try every provider once before giving up
        for _attempt in range(len(self.providers)):
            provider = self._get_next_provider()
            if not provider:
                raise RuntimeError("No AI providers configured")

            try:
                logger.info(f"→ {provider.name}")

                if provider.is_gemini:
                    result = await self._call_gemini(provider, system_prompt, user_prompt, json_mode)
                else:
                    result = await self._call_openai_compatible(provider, system_prompt, user_prompt, json_mode)

                # Success → reset failure count
                provider.failures = 0
                return result

            except Exception as e:
                error_str = str(e)
                provider.failures += 1
                provider.last_failure = time.time()
                errors.append(f"{provider.name}: {error_str[:120]}")

                is_rate_limit = any(kw in error_str.lower() for kw in ["429", "rate", "resource_exhausted", "quota"])
                if is_rate_limit:
                    logger.warning(f"⚡ Rate-limited on {provider.name} → rotating...")
                    await asyncio.sleep(1)
                else:
                    logger.error(f"✗ {provider.name}: {error_str[:200]}")
                    await asyncio.sleep(0.5)

        raise RuntimeError(
            f"All {len(self.providers)} AI provider slots failed:\n" +
            "\n".join(f"  • {e}" for e in errors)
        )


# ─── Singleton ────────────────────────────────────────────────────────

_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """Get or create the global LLM router singleton."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
