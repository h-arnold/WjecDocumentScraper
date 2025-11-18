# Gemini Batch API Usage

This document explains how to use the Gemini Batch API functionality in the WjecDocumentScraper project.

## Overview

The Gemini Batch API allows you to process multiple prompts asynchronously in a single batch job. This is useful for:
- Processing large volumes of requests efficiently
- Reducing API costs (batch requests are typically cheaper)
- Avoiding rate limits for bulk operations

## Key Concepts

The batch API is **asynchronous** and requires two separate operations:
1. **Create a batch job** - Submit multiple prompts for processing
2. **Fetch results** - Retrieve the completed results after the job finishes

Unlike synchronous `generate()` calls, batch jobs do not wait for completion. You must poll the job status separately and fetch results when ready.

## API Methods

### GeminiLLM Methods

#### `create_batch_job(batch_payload, *, filter_json=False) -> str`

Creates a batch job and returns the job name for tracking.

**Parameters:**
- `batch_payload`: Sequence of prompt sequences (e.g., `[["prompt1"], ["prompt2", "context"]]`)
- `filter_json`: Whether to apply JSON filtering to responses (default: False)

**Returns:** Batch job name (string) that can be used to track and fetch results

**Example:**
```python
from src.llm.gemini_llm import GeminiLLM

llm = GeminiLLM(system_prompt="prompts/categorise.md", filter_json=True)

batch_payload = [
    ["Categorize this document: Geography GCSE"],
    ["Categorize this document: French GCSE"],
    ["Categorize this document: Mathematics GCSE"],
]

job_name = llm.create_batch_job(batch_payload, filter_json=True)
print(f"Created batch job: {job_name}")
```

#### `get_batch_job(batch_job_name) -> BatchJob`

Gets the current status of a batch job.

**Parameters:**
- `batch_job_name`: The job name returned from `create_batch_job()`

**Returns:** BatchJob object with status information

**Example:**
```python
job = llm.get_batch_job(job_name)
print(f"Job state: {job.state}")
print(f"Job done: {job.done}")
```

#### `fetch_batch_results(batch_job_name) -> Sequence[Any]`

Fetches and parses results from a completed batch job.

**Parameters:**
- `batch_job_name`: The job name returned from `create_batch_job()`

**Returns:** Sequence of parsed responses in the same order as the original requests

**Raises:**
- `ValueError`: If the batch job is not completed yet
- `LLMProviderError`: If the job or individual requests failed

**Example:**
```python
# Wait for job to complete (implement your own polling strategy)
while not llm.get_batch_job(job_name).done:
    time.sleep(10)

# Fetch results
results = llm.fetch_batch_results(job_name)
for i, result in enumerate(results):
    print(f"Result {i}: {result}")
```

### LLMService Methods

The `LLMService` facade provides higher-level methods that work across multiple providers.

#### `create_batch_job(batch_payload, *, filter_json=False) -> tuple[str, str]`

Creates a batch job using the first available provider that supports batch operations.

**Parameters:**
- `batch_payload`: Sequence of prompt sequences
- `filter_json`: Whether to apply JSON filtering to responses

**Returns:** Tuple of `(provider_name, batch_job_name)` for tracking

**Example:**
```python
from src.llm.service import LLMService
from src.llm.gemini_llm import GeminiLLM

service = LLMService([
    GeminiLLM(system_prompt="prompts/categorise.md"),
])

provider_name, job_name = service.create_batch_job(batch_payload, filter_json=True)
print(f"Created job {job_name} with provider {provider_name}")
```

#### `get_batch_job_status(provider_name, batch_job_name) -> Any`

Gets the status of a batch job from a specific provider.

**Parameters:**
- `provider_name`: The provider name from `create_batch_job()`
- `batch_job_name`: The job name from `create_batch_job()`

**Returns:** Provider-specific batch job status object

**Example:**
```python
status = service.get_batch_job_status(provider_name, job_name)
print(f"Job done: {status.done}")
```

#### `fetch_batch_results(provider_name, batch_job_name) -> Sequence[Any]`

Fetches results from a completed batch job.

**Parameters:**
- `provider_name`: The provider name from `create_batch_job()`
- `batch_job_name`: The job name from `create_batch_job()`

**Returns:** Sequence of parsed responses

**Example:**
```python
results = service.fetch_batch_results(provider_name, job_name)
```

#### `cancel_batch_job(provider_name, batch_job_name) -> None`

Cancels a pending batch job.

**Parameters:**
- `provider_name`: The provider name from `create_batch_job()`
- `batch_job_name`: The job name from `create_batch_job()`

**Raises:**
- `ValueError`: If provider not found
- `NotImplementedError`: If provider doesn't support cancellation
- `LLMProviderError`: If cancellation fails

**Example:**
```python
# Cancel a job that's no longer needed
try:
    service.cancel_batch_job(provider_name, job_name)
    print(f"Cancelled job: {job_name}")
except LLMProviderError as e:
    print(f"Cancellation failed: {e}")
```

**Note:** Cancelling a job that has already completed or failed will raise an error. Check the job status before cancelling if needed.

## Complete Example

```python
import time
from src.llm.service import LLMService
from src.llm.gemini_llm import GeminiLLM

# Initialize service
service = LLMService([
    GeminiLLM(system_prompt="prompts/categorise.md", filter_json=True),
])

# Prepare batch requests
documents = [
    "Geography GCSE specification document",
    "French GCSE speaking assessment",
    "Mathematics GCSE past paper 2023",
]

batch_payload = [
    [f"Categorize this document: {doc}"]
    for doc in documents
]

# Create batch job
print("Creating batch job...")
provider_name, job_name = service.create_batch_job(batch_payload, filter_json=True)
print(f"Created job: {job_name}")

# Poll for completion (implement your own polling strategy)
print("Waiting for completion...")
while True:
    status = service.get_batch_job_status(provider_name, job_name)
    if status.done:
        break
    print(f"  Status: {status.state}")
    time.sleep(10)

# Fetch results
print("Fetching results...")
results = service.fetch_batch_results(provider_name, job_name)

# Process results
for i, (doc, result) in enumerate(zip(documents, results)):
    print(f"\nDocument: {doc}")
    print(f"Category: {result}")
```

## Configuration

Batch requests use the same configuration as synchronous requests:
- **Model:** `gemini-2.5-flash` (from `GeminiLLM.MODEL`)
- **Temperature:** 0.2
- **Thinking budget:** 24576 tokens (from `GeminiLLM.MAX_THINKING_BUDGET`)
- **System prompt:** Specified when creating the `GeminiLLM` instance

## Response Format

Batch results are formatted consistently with synchronous `generate()` responses:
- If `filter_json=False`: Raw response objects
- If `filter_json=True`: Parsed JSON objects (trailing commas removed, etc.)

## Error Handling

The batch API can raise several types of errors:

1. **ValueError**: Empty batch payload, incomplete job, or missing results
2. **LLMProviderError**: Job failed or individual requests failed
3. **NotImplementedError**: Provider doesn't support batch operations

Always wrap batch operations in try-except blocks:

```python
try:
    results = service.fetch_batch_results(provider_name, job_name)
except ValueError as e:
    print(f"Job not ready: {e}")
except LLMProviderError as e:
    print(f"Processing failed: {e}")
```

## Limitations

- No built-in polling strategy - you must implement your own
- The `batch_generate()` method is **not supported** and raises `NotImplementedError`
- Batch jobs are provider-specific - you must use the same provider for creation and fetching

## Refetching Recently Completed Batches

Sometimes you may want to reprocess batches that were recently completed (for example, to test a new prompt or fix a processing issue). The `batch-fetch` command supports a `--refetch-hours` option that allows you to refetch and reprocess batches completed within a specified time window.

### How It Works

When you use `--refetch-hours`, the system:
1. Identifies all batch jobs completed within the specified number of hours
2. Resets their status from "completed" back to "pending" in the tracking file
3. Removes their completion markers from the state file
4. Processes them as if they were being fetched for the first time

This means the batch results will be re-fetched from the API and reprocessed through the validation and persistence logic.

### Usage

```bash
# Refetch batches completed in the last 6 hours
python -m src.llm_review.llm_categoriser batch-fetch --refetch-hours 6

# Refetch batches completed in the last 24 hours
python -m src.llm_review.llm_categoriser batch-fetch --refetch-hours 24

# Refetch batches completed in the last 30 minutes
python -m src.llm_review.llm_categoriser batch-fetch --refetch-hours 0.5
```

### Example Output

```
Found 3 job(s) completed within last 6.0 hour(s)
Reset batches/abc123... (Geography/gcse-geography.md batch 0) to pending
Reset batches/def456... (History/gcse-history.md batch 1) to pending
Reset batches/ghi789... (Math/gcse-math.md batch 0) to pending

Checking 3 job(s)...

Job batches/abc123... (Geography/gcse-geography.md batch 0)
  Status: SUCCEEDED (still pending)
  Saved 10 result(s) to Documents/Geography/language-issues/gcse-geography.jsonl

Job batches/def456... (History/gcse-history.md batch 1)
  Status: SUCCEEDED (still pending)
  Saved 15 result(s) to Documents/History/language-issues/gcse-history.jsonl

Job batches/ghi789... (Math/gcse-math.md batch 0)
  Status: SUCCEEDED (still pending)
  Saved 8 result(s) to Documents/Math/language-issues/gcse-math.jsonl

============================================================
Summary:
  Checked: 3
  Completed: 3
  Failed: 0
  Still pending: 0
  Refetched: 3
============================================================
```

### Use Cases

- **Testing prompt changes**: Reprocess recent batches with a modified prompt to see how results change
- **Fixing processing bugs**: If you discover a bug in validation or persistence logic, refetch recent batches to correct the data
- **Re-validating results**: Double-check recent categorizations if you're not confident in the quality
- **Recovering from errors**: If some batches failed during initial processing, refetch them after fixing the issue

### Important Notes

- The `--refetch-hours` parameter accepts floating-point values (e.g., `0.5` for 30 minutes)
- Only jobs with status "completed" will be refetched; pending and failed jobs are not affected
- The time window is calculated from the job's `created_at` timestamp
- Refetching does not create new API batch jobs; it re-fetches existing results from already-completed jobs
- Cannot be combined with `--job-names` or `--check-all-pending` (use one method at a time)

## Best Practices

1. **Store job metadata**: Save the provider name and job name immediately after creation
2. **Implement exponential backoff**: When polling, increase wait time gradually
3. **Handle partial failures**: Individual requests can fail even if the job succeeds
4. **Use appropriate batch sizes**: Large batches may take longer to process
5. **Monitor costs**: Batch requests still consume API quota
