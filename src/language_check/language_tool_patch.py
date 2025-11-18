"""Monkey-patch for language_tool_python to use POST requests.

The default language_tool_python library uses GET requests which send all
parameters (including the document text) in the URL query string. For large
documents (>300KB), this exceeds HTTP server limits and causes connection
resets.

This patch replaces the _query_server method to use POST requests instead,
which send data in the request body and have much higher size limits.
"""

from __future__ import annotations

import http.client
import json
from typing import Any, Dict, Optional

import requests
from language_tool_python.server import DEBUG_MODE
from language_tool_python.utils import LanguageToolError, RateLimitError


def _query_server_post(
    self: Any,
    url: str,
    params: Optional[Dict[str, str]] = None,
    num_tries: int = 2,
) -> Any:
    """
    Query the LanguageTool server using POST requests instead of GET.

    This is a replacement for language_tool_python.server.LanguageTool._query_server
    that uses POST requests to avoid URL length limitations with large documents.

    :param self: The LanguageTool instance
    :param url: The URL to query
    :param params: The parameters to include in the request body
    :param num_tries: The number of times to retry the query
    :return: The JSON response from the server
    :raises LanguageToolError: If the query fails after all retries
    """
    if DEBUG_MODE:
        print(
            "_query_server_post url:",
            url,
            "params keys:",
            list(params.keys()) if params else None,
        )
        if params and "text" in params:
            print(f"  text length: {len(params['text'])} characters")

    for n in range(num_tries):
        try:
            # Use POST instead of GET, sending params as form data
            with requests.post(
                url,
                data=params,  # Send as form data in body instead of URL params
                timeout=self._TIMEOUT,
            ) as response:
                try:
                    return response.json()
                except json.decoder.JSONDecodeError as e:
                    if DEBUG_MODE:
                        print(f"URL {url} returned invalid JSON response: {e}")
                        print(response)
                        print(response.content)
                    if response.status_code == 426:
                        raise RateLimitError(
                            "You have exceeded the rate limit for the free "
                            "LanguageTool API. Please try again later."
                        ) from e
                    raise LanguageToolError(response.content.decode()) from e
        except (IOError, http.client.HTTPException) as e:
            if self._remote is False:
                self._terminate_server()
                self._start_local_server()
            if n + 1 >= num_tries:
                raise LanguageToolError(f"{self._url}: {e}") from e
    return None


def apply_post_request_patch() -> None:
    """
    Apply the POST request patch to language_tool_python.LanguageTool.

    This replaces the _query_server method with one that uses POST requests
    instead of GET requests, allowing large documents to be checked without
    hitting URL length limits.
    """
    import language_tool_python.server as lt_server

    # Store the original method in case we need to revert
    if not hasattr(lt_server.LanguageTool, "_query_server_original"):
        lt_server.LanguageTool._query_server_original = (
            lt_server.LanguageTool._query_server
        )

    # Replace with the POST version
    lt_server.LanguageTool._query_server = _query_server_post

    if DEBUG_MODE:
        print("Applied POST request patch to language_tool_python.LanguageTool")


def revert_post_request_patch() -> None:
    """
    Revert the POST request patch, restoring the original GET request behavior.
    """
    import language_tool_python.server as lt_server

    if hasattr(lt_server.LanguageTool, "_query_server_original"):
        lt_server.LanguageTool._query_server = (
            lt_server.LanguageTool._query_server_original
        )
        delattr(lt_server.LanguageTool, "_query_server_original")

        if DEBUG_MODE:
            print("Reverted POST request patch from language_tool_python.LanguageTool")
