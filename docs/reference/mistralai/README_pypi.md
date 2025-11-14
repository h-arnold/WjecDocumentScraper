# Mistral Python SDK — local reference (from PyPI)

Source: https://pypi.org/project/mistralai/
Official docs: https://docs.mistral.ai/
GitHub: https://github.com/mistralai/client-python

This file is a local reference copy of the `mistralai` PyPI project description and key usage bits (trimmed).

## Package name / install
- PyPI package: `mistralai` (current versions as of 2025)

Recommended install methods shown on PyPI:
- uv (recommended in this workspace):

  uv add mistralai

- pip:

  pip install mistralai

- poetry:

  poetry add mistralai

Extras:
- Agents features: `mistralai[agents]` (requires Python >= 3.10 for some deps)
- Google Cloud: `mistralai[gcp]`

## Quick examples (synopsis from PyPI)

Synchronous chat example:

```py
from mistralai import Mistral
import os

with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
    res = mistral.chat.complete(
        model="mistral-small-latest",
        messages=[{"content": "Who is the best French painter? Answer in one short sentence.", "role": "user"}],
        stream=False,
    )
    print(res)
```

Asynchronous example:

```py
import asyncio
from mistralai import Mistral
import os

async def main():
    async with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
        res = await mistral.chat.complete_async(
            model="mistral-small-latest",
            messages=[{"content": "Who is the best French painter? Answer in one short sentence.", "role": "user"}],
            stream=False,
        )
        print(res)

asyncio.run(main())
```

Embeddings example (sync):

```py
from mistralai import Mistral
import os

with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
    res = mistral.embeddings.create(model="mistral-embed", inputs=["Embed this sentence.", "And this one."])
    print(res)
```

File upload example (sync):

```py
from mistralai import Mistral
import os

with Mistral(api_key=os.getenv("MISTRAL_API_KEY", "")) as mistral:
    res = mistral.files.upload(file={
        "file_name": "example.file",
        "content": open("example.file", "rb"),
    })
    print(res)
```

## Notes / useful links
- Full docs and cookbooks: https://docs.mistral.ai/
- PyPI project page (this copy source): https://pypi.org/project/mistralai/
- GitHub client repo: https://github.com/mistralai/client-python

## Local copy metadata
- Retrieved: November 14, 2025
- Retrieved from PyPI project description; trimmed for readability.

---

(End of local reference copy)
