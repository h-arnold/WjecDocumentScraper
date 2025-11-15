"""Shared JSON extraction and repair utilities for LLM providers.

This module provides common functionality for parsing JSON from LLM responses,
including repair of malformed JSON and extraction from text that may contain
additional commentary or code fences.
"""

from __future__ import annotations

import json
from typing import Any

from json_repair import repair_json


def parse_json_response(text: str) -> Any:
    """Extract and repair JSON content from LLM response text.
    
    This function:
    1. Locates JSON object delimiters (outermost { and })
    2. Extracts the JSON fragment
    3. Repairs common JSON formatting issues
    4. Parses and returns the result
    
    Args:
        text: The response text from an LLM that should contain JSON
        
    Returns:
        The parsed JSON object (typically a dict or list)
        
    Raises:
        ValueError: If JSON delimiters are not found or text is invalid
        json.JSONDecodeError: If the repaired text still cannot be parsed
        
    Example:
        >>> text = "Here's the result: {\"key\": \"value\"} Thanks!"
        >>> result = parse_json_response(text)
        >>> result["key"]
        'value'
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected string input, got {type(text)}")
    
    # Find outermost JSON fragment delimiters. Support objects ({...}) and
    # arrays ([...]) at the top level. Choose whichever appears first in
    # the response text (e.g. we prefer an array if it occurs before an object).
    start_obj = text.find("{")
    start_arr = text.find("[")

    # Choose the earliest valid start index (that isn't -1), preferring
    # arrays if they both exist at the same position.
    if start_obj == -1 and start_arr == -1:
        raise ValueError("Response text does not contain JSON object or array delimiters.")

    if start_obj == -1:
        start = start_arr
        end_char = "]"
    elif start_arr == -1:
        start = start_obj
        end_char = "}"
    else:
        # Both are present; choose whichever comes first
        if start_arr < start_obj:
            start = start_arr
            end_char = "]"
        else:
            start = start_obj
            end_char = "}"

    end = text.rfind(end_char)

    if end == -1 or end <= start:
        raise ValueError("Response text does not contain matching JSON delimiters.")
    
    # Extract the JSON fragment
    json_fragment = text[start : end + 1]
    
    # Repair common JSON formatting issues
    repaired = repair_json(json_fragment)
    
    # Parse and return
    return json.loads(repaired)
