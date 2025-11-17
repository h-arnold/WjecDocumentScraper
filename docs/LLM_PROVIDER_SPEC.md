# LLM Provider Contract and Fallback Design

## Purpose

This document captures the requirements, interface contract, and orchestration patterns that should govern any LLM integration inside `WjecDocumentScraper`. It is explicitly written to accommodate parallel LLM providers (currently Gemini and Mistral), to support both live and batch APIs, and to make switching between providers transparent when quota limits or throttling errors occur.

## Context

- The existing `GeminiLLM` wrapper in `src/llm/gemini_llm.py` handles system prompts, dotenv-based credentials, filtering JSON, and talking to Google GenAI.
- Because the user is on the free tiers for both Gemini and Mistral, hitting request/token limits is expected. The runtime needs an orchestrator that can fall back from the primary provider to an alternate provider (or queue requests) without breaking the caller's experience.
- Gemini and Mistral expose **different API flavors** (single-response vs. batch endpoints), so the interface must expose both live and batch flows in a single contract while letting each provider opt into the behaviors they support.

## Requirements

1. **Single responsibility**: Each provider wrapper must own provider-specific details (client creation, prompt formatting, response parsing, batch orchestration, error translation).
2. **Shared contract**: Callers should use a provider-agnostic `LLMProvider` interface. They must not import Google or Mistral SDK types directly after refactor.
3. **Batch / live separation**: Providers must expose both `generate` (live) and `batch_generate` (async or multi-prompt) entry points. Providers that lack batch support should raise `NotImplementedError` to signal the orchestrator.
4. **Quota-aware fallback**: When one provider raises a well-known quota or rate-limit exception (`QuotaExceededError`, `RateLimitError`, etc.), the orchestrator must retry the request with the next provider without delegating error handling to the caller.
5. **Fail-fast when all providers exhausted**: If every provider in the configured list rejects a request due to quota, the orchestrator should raise a consolidated `LLMQuotaError` so the CLI or caller can expose an informative message.
6. **Configurable priority**: The provider order should be declarative (via settings or a tuple), enabling future CLI flags (e.g. `--prefers mistral`) or environment toggles.
7. **Observability hooks**: Providers should surface optional hooks/callbacks for reporting (provider name, success/failure, latency, quota state) to integrate with existing progress reporting.

## Contract: `LLMProvider`

```python
class LLMProvider(Protocol):
    name: str

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool = False,
    ) -> Any:
        """Produce a response for a live request. """

    def batch_generate(
        self,
        batch_payload: Sequence[Sequence[str]],
        *,
        filter_json: bool = False,
    ) -> Sequence[Any]:
        """Handle batch requests. Providers without batch APIs should raise NotImplementedError."""

    def health_check(self) -> bool:
        """Optional: quick noop to verify credentials or rate-limit status."""
```

### Contract notes

- `name` should match the provider identifier used in configuration (`"gemini"`, `"mistral"`, …).
- Implementations should wrap provider-specific errors into shared exceptions (`LLMProviderError`, `QuotaExceededError`) so the orchestrator can detect quota issues without importing SDK-specific classes.
- `generate` and `batch_generate` share `filter_json` to keep response normalization consistent.
- Providers may record metadata (latency, tokens) via callbacks passed in, but this is optional for the current project.

## Common exception hierarchy

```python
class LLMProviderError(Exception):
    """Generic provider failure."""

class LLMQuotaError(LLMProviderError):
    """Raised when the provider quota/rate limit is exhausted."""

class LLMProviderConfigurationError(LLMProviderError):
    """Raised during setup (missing credentials, invalid prompt)."""
```

- Each provider must translate provider-specific quota or rate-limit responses into `LLMQuotaError`. For Gemini, this may mean inspecting `response.error.code` or similar.
- The orchestrator treats `LLMQuotaError` specially (see fallback below), and surfaces other subclasses for logging.

## Orchestrator: `LLMService`

The orchestrator/facade handles provider sequencing, fallback logic, and delegation of batch/live requests. Example signature:

```python
class LLMService:
    def __init__(self, providers: Sequence[LLMProvider]) -> None:
        self.providers = list(providers)

    def generate(
        self,
        user_prompts: Sequence[str],
        *,
        filter_json: bool = False,
    ) -> Any:
        last_error = None
        for provider in self.providers:
            try:
                return provider.generate(user_prompts, filter_json=filter_json)
            except LLMQuotaError as exc:
                last_error = exc
                continue
            except LLMProviderError:
                raise
        raise LLMQuotaError("All providers exceeded quota") from last_error
```

- `batch_generate` mirrors this logic while skipping providers that raise `NotImplementedError`.
- Optional hooks:
  - `report_provider(name, status, error=None)` for logging.
  - `provider_order()` to show current fallback order in CLI help.

## Provider behaviors

### Gemini
- Implements both `generate` and `batch_generate` (if the SDK supports `batchGenerateContent`). If no batch API is available yet, `batch_generate` should explicitly raise `NotImplementedError` so orchestrator skips it.
- Handles system prompt loading and `filter_json` via `_parse_response_json` (current logic).
- Wraps quota errors (likely HTTP 429 or API-specific codes) into `LLMQuotaError`.
- Exposes `LLMProvider.name = "gemini"` and a `health_check` that verifies available API key.

### Mistral
- Implemented in `src/llm/mistral_llm.py` with both `generate` (live) and `batch_generate` pathways.
- `generate` uses `client.beta.conversations.start` and always supplies the system prompt via `instructions` plus a single merged user message. JSON output is normalised through `parse_json_response` when `filter_json=True`.
- `batch_generate` writes a JSONL file containing one request per prompt group. Each line matches the Conversations API schema: `{"custom_id": "req-00001", "method": "POST", "url": "/v1/conversations", "body": {"instructions": ..., "inputs": [{"type": "message.input", "role": "user", "content": "..."}], "completion_args": {"temperature": 0.2}, "tools": []}}`.
- The JSONL file is uploaded via `files.upload(purpose="batch")`, the resulting file id is submitted to `batch.jobs.create(endpoint="/v1/conversations", model="magistral-medium-latest")`, and polling continues until the job reaches a terminal status. Successful jobs download the `output_file` and convert each line back into either a `ConversationResponse` or parsed JSON (when filtering is enabled).
- Non-success statuses assemble details from `job.errors` and the optional `error_file`, raising `LLMProviderError`. HTTP 429 responses encountered during upload, job creation, polling, or downloads are mapped to `LLMQuotaError` so the orchestrator can fall back to the next provider.

## Batch vs. Live APIs

- **Live**: One `generate` call per sequence of prompts. Suitable for CLI calls that need immediate output (e.g., prompt conversion to Markdown).
- **Batch**: Accepts a sequence of prompt groups, returning a list of responses. This is useful for CLI workflows that process multiple documents/sections at once.
- The orchestrator should allow callers to express the request shape (`Sequence[str]` vs. `Sequence[Sequence[str]]`).
- For JSON filtering, the boolean flag stays consistent between live & batch, so wrappers can reuse `_parse_response_json`.

## Dynamic provider switching

1. `LLMService.generate` tries providers in configured order.
2. On `LLMQuotaError`, move to the next provider and log the event (with provider name and quota details).
3. If a provider raises `NotImplementedError` for batch requests, skip it rather than failing immediately.
4. After exhausting all providers, raise `LLMQuotaError` so higher layers can request the user to try again later.
5. Consider emitting a summary (e.g., `"primary Gemini quota exceeded, using fallback"`) for CLI progress reporting.

## Configuration & Extension

- Add a small factory or registry (e.g., `llm/provider_registry.py`) that wires the providers based on environment variables (`LLM_PRIMARY=gemini`, `LLM_FALLBACK=mistral`) and optional CLI flags.
- Document how to add a new provider:
  1. Create a new module implementing `LLMProvider`.
  2. Add it to the registry and expose a factory.
  3. Implement batch/live methods and error translation.
  4. Update tests/fixtures to use the new provider name.

## Testing & Observability

- Unit tests should mock each provider and verify that `LLMService` retries on `LLMQuotaError` while honoring the configured order.
- Documented diagnostics should include:
  - Provider name + status (success/failure/quota)
  - Which provider is currently used for a request
  - The exact error message when quota is hit

## Environment variables

- `MISTRAL_API_KEY` (required): API key loaded via `dotenv` or the process environment; needed for both live and batch calls.
- `MISTRAL_BATCH_POLL_INTERVAL` (optional, default `2.0` seconds): controls how often the batch runner polls `batch.jobs.get` while waiting for a terminal state.
- `MISTRAL_BATCH_TIMEOUT` (optional, default `900` seconds): maximum wall-clock duration to wait for a batch job before surfacing a `LLMProviderError`.
- `LLM_FAIL_ON_QUOTA`, `LLM_PRIMARY`, `LLM_FALLBACK`: existing orchestrator tuning flags described in `docs/DEV_WORKFLOWS.md`.

The batch-specific variables allow longer-running jobs (for large prompt sets) to complete without code changes while keeping short runs responsive during development.

## Summary

This contract ensures we can add and orchestrate multiple LLM providers (Gemini, Mistral, later others) while handling quota limits gracefully. The interface enforces symmetry between live/batch flows, and the orchestrator keeps callers simple by automatically switching providers when needed. Use `docs/LLM_PROVIDER_SPEC.md` as the single source of truth whenever you add or change provider logic.
