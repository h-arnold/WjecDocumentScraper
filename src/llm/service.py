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

    def create_batch_job(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> tuple[str, str]:
        """Create a batch job using the first available provider that supports it.
        
        Args:
            batch_payload: Sequence of prompt sequences.
            filter_json: Whether to apply JSON filtering to responses.
        
        Returns:
            Tuple of (provider_name, batch_job_name) for tracking and retrieval.
        
        Raises:
            NotImplementedError: If no provider supports batch job creation.
            LLMProviderError: If batch job creation fails.
        """
        last_error: Exception | None = None
        for provider in self._providers:
            # Check if provider has create_batch_job method
            if not hasattr(provider, 'create_batch_job'):
                self._report(provider.name, ProviderStatus.UNSUPPORTED)
                continue
            
            try:
                batch_job_name = provider.create_batch_job(
                    batch_payload, 
                    filter_json=filter_json
                )
                self._report(provider.name, ProviderStatus.SUCCESS)
                return (provider.name, batch_job_name)
            except NotImplementedError:
                self._report(provider.name, ProviderStatus.UNSUPPORTED)
                continue
            except LLMQuotaError as exc:
                last_error = exc
                self._report(provider.name, ProviderStatus.QUOTA, exc)
                continue
            except LLMProviderError as exc:
                self._report(provider.name, ProviderStatus.FAILURE, exc)
                raise
        
        raise NotImplementedError("No provider supports create_batch_job")

    def fetch_batch_results(
        self,
        provider_name: str,
        batch_job_name: str,
    ) -> Sequence[Any]:
        """Fetch results from a completed batch job.
        
        Args:
            provider_name: The name of the provider that created the batch job.
            batch_job_name: The batch job identifier returned from create_batch_job.
        
        Returns:
            Sequence of parsed responses in the same order as the original requests.
        
        Raises:
            ValueError: If provider not found or batch job not completed.
            LLMProviderError: If fetching results fails.
        """
        provider = self._find_provider(provider_name)
        
        if not hasattr(provider, 'fetch_batch_results'):
            raise NotImplementedError(
                f"Provider '{provider_name}' does not support fetch_batch_results"
            )
        
        try:
            results = provider.fetch_batch_results(batch_job_name)
            self._report(provider.name, ProviderStatus.SUCCESS)
            return results
        except LLMProviderError as exc:
            self._report(provider.name, ProviderStatus.FAILURE, exc)
            raise

    def get_batch_job_status(
        self,
        provider_name: str,
        batch_job_name: str,
    ) -> Any:
        """Get the status of a batch job.
        
        Args:
            provider_name: The name of the provider that created the batch job.
            batch_job_name: The batch job identifier returned from create_batch_job.
        
        Returns:
            Provider-specific batch job status object.
        
        Raises:
            ValueError: If provider not found.
            LLMProviderError: If getting status fails.
        """
        provider = self._find_provider(provider_name)
        
        if not hasattr(provider, 'get_batch_job'):
            raise NotImplementedError(
                f"Provider '{provider_name}' does not support get_batch_job"
            )
        
        try:
            status = provider.get_batch_job(batch_job_name)
            self._report(provider.name, ProviderStatus.SUCCESS)
            return status
        except LLMProviderError as exc:
            self._report(provider.name, ProviderStatus.FAILURE, exc)
            raise

    def _find_provider(self, provider_name: str) -> LLMProvider:
        """Find a provider by name.
        
        Args:
            provider_name: The name of the provider to find.
        
        Returns:
            The provider with the given name.
        
        Raises:
            ValueError: If provider not found.
        """
        provider = next((p for p in self._providers if p.name == provider_name), None)
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' not found in service")
        return provider

    def _report(
        self,
        provider_name: str,
        status: ProviderStatus,
        error: Exception | None = None,
    ) -> None:
        if self._reporter is None:
            return
        self._reporter(provider_name, status, error)