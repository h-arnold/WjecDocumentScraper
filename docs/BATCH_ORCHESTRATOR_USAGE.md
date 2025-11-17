# Batch Orchestrator Usage Guide

This guide explains how to use the batch orchestrator for asynchronous LLM categorisation using the Gemini Batch API.

## Overview

The batch orchestrator enables processing language issues through the Gemini Batch API, allowing you to:
- Create batch jobs for multiple documents/subjects
- Track job status and metadata
- Fetch completed results and integrate them with the existing workflow

## Quick Start

### 1. Create Batch Jobs

Process all documents in the report:
```bash
python -m src.llm_review.llm_categoriser batch-create
```

Process specific subjects:
```bash
python -m src.llm_review.llm_categoriser batch-create --subjects Geography "Art and Design"
```

Process specific documents:
```bash
python -m src.llm_review.llm_categoriser batch-create --documents gcse-geography.md
```

Custom batch size:
```bash
python -m src.llm_review.llm_categoriser batch-create --batch-size 5
```

### 2. Check Job Status

List all tracked jobs:
```bash
python -m src.llm_review.llm_categoriser batch-list
```

List only pending jobs:
```bash
python -m src.llm_review.llm_categoriser batch-list --status pending
```

List completed jobs:
```bash
python -m src.llm_review.llm_categoriser batch-list --status completed
```

### 3. Fetch Completed Results

Check and fetch all pending jobs:
```bash
python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
```

Fetch specific job by name:
```bash
python -m src.llm_review.llm_categoriser batch-fetch --job-names batch-123
```

Fetch multiple specific jobs:
```bash
python -m src.llm_review.llm_categoriser batch-fetch --job-names batch-123 batch-456 batch-789
```

## Workflow

### Complete Workflow Example

1. **Create batch jobs for all Geography documents:**
   ```bash
   python -m src.llm_review.llm_categoriser batch-create --subjects Geography
   ```
   
   Output:
   ```
   Processing Geography/gcse-geography.md (45 issues)...
     Batch 0: Created job batch-abc123...
     Batch 1: Created job batch-def456...
   Summary:
     Total documents: 1
     Total batches: 2
     Created jobs: 2
   ```

2. **Wait for jobs to complete** (polling strategy depends on your needs - manual check or automated script)

3. **Check job status:**
   ```bash
   python -m src.llm_review.llm_categoriser batch-list --status pending
   ```

4. **Fetch completed results:**
   ```bash
   python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
   ```
   
   Output:
   ```
   Job batch-abc123... (Geography/gcse-geography.md batch 0)
     Saved 10 result(s) to Documents/Geography/document_reports/gcse-geography.csv
   Job batch-def456... (Geography/gcse-geography.md batch 1)
     Status: RUNNING (still pending)
   Summary:
     Checked: 2
     Completed: 1
     Failed: 0
     Still pending: 1
   ```

5. **Run again to fetch remaining jobs:**
   ```bash
   python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
   ```

## Configuration

### Environment Variables

Same environment variables as synchronous mode:
- `LLM_CATEGORISER_BATCH_SIZE`: Default batch size (default: 10)
- `LLM_PRIMARY`: Primary LLM provider (default: gemini)
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: API key for Gemini

### Custom Files

Tracking file (stores job metadata):
```bash
python -m src.llm_review.llm_categoriser batch-create --tracking-file data/my_jobs.json
python -m src.llm_review.llm_categoriser batch-fetch --tracking-file data/my_jobs.json --check-all-pending
```

State file (tracks completed batches):
```bash
python -m src.llm_review.llm_categoriser batch-fetch --state-file data/my_state.json --check-all-pending
```

## Job Metadata

Each batch job stores:
- **provider_name**: LLM provider that created the job
- **job_name**: Unique job identifier
- **subject**: Subject name (e.g., "Geography")
- **filename**: Document filename (e.g., "gcse-geography.md")
- **batch_index**: Zero-based batch index within the document
- **issue_ids**: List of issue IDs in this batch
- **created_at**: ISO timestamp when job was created
- **status**: "pending", "completed", or "failed"

This metadata enables proper integration with the existing state tracking and document report generation.

## Output

Batch results are saved to the same location as synchronous results:
```
Documents/<subject>/document_reports/<filename>.csv
```

The state file tracks completed batches, enabling resume support:
```json
{
  "version": "1.0",
  "subjects": {
    "Geography": {
      "gcse-geography.md": {
        "completed_batches": [0, 1, 2],
        "total_issues": 45
      }
    }
  }
}
```

## Comparison with Synchronous Mode

### Synchronous Mode
```bash
python -m src.llm_review.llm_categoriser --subjects Geography
```
- Processes batches immediately, waiting for each response
- Blocks until all batches complete
- Good for small datasets or immediate results

### Batch Mode
```bash
# Create jobs
python -m src.llm_review.llm_categoriser batch-create --subjects Geography

# Wait (manual or automated polling)

# Fetch results
python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
```
- Submits all batches at once
- Non-blocking - can process other work while waiting
- Good for large datasets or cost optimization

## Error Handling

### Job Creation Errors
If a job fails to create, it's skipped and logged:
```
Batch 2: Failed to create job - Provider quota exhausted
```

The orchestrator continues with remaining batches.

### Job Fetch Errors
If a job fails during execution, it's marked as "failed":
```
Job batch-xyz... (Geography/gcse-geography.md batch 2)
  Error processing job: Batch job batch-xyz failed: Invalid response format
```

Failed jobs can be retried manually or by recreating them with `batch-create --force`.

### Validation Errors
If individual issues fail validation, they're logged but don't fail the entire batch:
```
Warning: Issue ID 999 not in batch, skipping
Warning: Issue 42 missing required fields
```

## Advanced Usage

### Resume Support

The orchestrator integrates with the existing state tracking system. If you run `batch-create` again:
- It will create jobs for all batches (no automatic skip logic)
- Use filters to avoid recreating jobs

To completely reprocess:
1. Clear tracking file: `rm data/batch_jobs.json`
2. Clear state: Use `--force` with synchronous mode or manually clear `data/llm_categoriser_state.json`
3. Create new batch jobs

### Polling Strategy

The orchestrator doesn't include automated polling. Implement your own:

```bash
#!/bin/bash
# Simple polling script
while true; do
    echo "Checking batch jobs..."
    python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
    
    # Check if any pending jobs remain
    pending=$(python -m src.llm_review.llm_categoriser batch-list --status pending | grep -c "job-")
    
    if [ "$pending" -eq 0 ]; then
        echo "All jobs completed!"
        break
    fi
    
    echo "Waiting 60 seconds..."
    sleep 60
done
```

### Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Create batch jobs
  run: python -m src.llm_review.llm_categoriser batch-create

- name: Wait for completion
  run: |
    while [ "$(python -m src.llm_review.llm_categoriser batch-list --status pending | grep -c 'job-')" -gt 0 ]; do
      sleep 60
      python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
    done

- name: Commit results
  run: |
    git add Documents/*/document_reports/*.csv
    git commit -m "Update categorisation results"
```

## Troubleshooting

### "No jobs specified"
You need to specify which jobs to fetch:
```bash
python -m src.llm_review.llm_categoriser batch-fetch --check-all-pending
```

### "Provider not found"
The tracking file references a provider that's not configured. Check your environment variables and ensure the same provider is available when fetching.

### "No results returned"
The batch job completed but returned no results. Check the Gemini API console for job details.

### Jobs stuck in "pending"
Batch jobs can take time. Check:
1. Job status in Gemini API console
2. Quota limits
3. Job creation time (may still be processing)

## Best Practices

1. **Start small**: Test with `--subjects` or `--documents` filters first
2. **Monitor quotas**: Batch API has separate quotas from synchronous API
3. **Check status regularly**: Use `batch-list` to monitor progress
4. **Handle failures gracefully**: Check for failed jobs and retry if needed
5. **Keep tracking files**: Don't delete `data/batch_jobs.json` until all jobs are fetched
6. **Use version control**: Commit tracking files if coordinating across machines
