# Batch API Quick Reference

## Basic Workflow

```python
from src.llm.service import LLMService
from src.llm.gemini_llm import GeminiLLM

# 1. Initialize service
service = LLMService([
    GeminiLLM(system_prompt="prompts/categorise.md", filter_json=True),
])

# 2. Create batch job
batch_payload = [
    ["prompt 1"],
    ["prompt 2", "additional context"],
    ["prompt 3"],
]
provider_name, job_name = service.create_batch_job(batch_payload, filter_json=True)

# 3. Check status (implement your polling strategy)
status = service.get_batch_job_status(provider_name, job_name)
if status.done:
    # 4. Fetch results
    results = service.fetch_batch_results(provider_name, job_name)
```

## Key Points

✅ **DO:**
- Store the provider_name and job_name immediately after creation
- Implement your own polling strategy to check when job is done
- Use the same provider for creation and fetching
- Handle errors gracefully (job may fail or be incomplete)

❌ **DON'T:**
- Don't call `batch_generate()` - it raises NotImplementedError
- Don't fetch results before checking if job is done
- Don't assume all requests succeeded - check for errors

## Configuration Match

Batch requests automatically use the same configuration as synchronous requests:
- Model: `gemini-2.5-flash`
- Temperature: `0.2`
- Thinking budget: `24576` tokens
- System prompt: From GeminiLLM initialization

## Response Format

- `filter_json=False`: Returns raw response objects
- `filter_json=True`: Returns parsed JSON (trailing commas removed)

Results are returned in the same order as the input batch_payload.
