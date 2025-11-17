from __future__ import annotations

from typing import Any, Sequence

from .provider import (
    LLMProvider,
    LLMProviderError,
    LLMQuotaError,
    ProviderReporter,
    ProviderStatus,
)


class LLMService:
    """Facade that routes LLM requests across a priority-ordered provider list."""

    def __init__(
        self,
        providers: Sequence[LLMProvider],
        *,
        reporter: ProviderReporter | None = None,
    ) -> None:
        self._providers = list(providers)
        self._reporter = reporter

    def provider_order(self) -> list[str]:
        """Return the provider names in configured order."""

        return [provider.name for provider in self._providers]

    def health_check(self) -> list[tuple[str, bool]]:
        """Run the optional health check for every provider."""

        return [(provider.name, provider.health_check()) for provider in self._providers]

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool = False,
    ) -> Any:
        """Try each provider until one succeeds or all quotas are exhausted."""

        last_error: LLMQuotaError | None = None
        for provider in self._providers:
            try:
                value = provider.generate(user_prompts, filter_json=filter_json)
                self._report(provider.name, ProviderStatus.SUCCESS)
                return value
            except LLMQuotaError as exc:
                last_error = exc
                self._report(provider.name, ProviderStatus.QUOTA, exc)
                continue
            except LLMProviderError as exc:
                self._report(provider.name, ProviderStatus.FAILURE, exc)
                raise
        raise LLMQuotaError("All providers exceeded quota") from last_error

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        """Try each provider until one supports batch requests or all quotas are exhausted."""

        last_error: LLMQuotaError | None = None
        attempted = False
        for provider in self._providers:
            try:
                result = provider.batch_generate(batch_payload, filter_json=filter_json)
            except NotImplementedError:
                self._report(provider.name, ProviderStatus.UNSUPPORTED)
                continue
            except LLMQuotaError as exc:
                attempted = True
                last_error = exc
                self._report(provider.name, ProviderStatus.QUOTA, exc)
                continue
            except LLMProviderError as exc:
                attempted = True
                self._report(provider.name, ProviderStatus.FAILURE, exc)
                raise
            else:
                attempted = True
                self._report(provider.name, ProviderStatus.SUCCESS)
                return result
        if not attempted:
            raise NotImplementedError("No provider supports batch_generate")
        raise LLMQuotaError("All providers exceeded quota") from last_error

    def _report(
        self,
        provider_name: str,
        status: ProviderStatus,
        error: Exception | None = None,
    ) -> None:
        if self._reporter is None:
            return
        self._reporter(provider_name, status, error)