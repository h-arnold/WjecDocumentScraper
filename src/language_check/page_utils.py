"""Shim to re-export page utilities from ``src.utils``.

This file preserves the expected relative import path used by
``language_check.py`` when the module was previously inside
``src.utils``.
"""

from __future__ import annotations

from src.utils.page_utils import build_page_number_map

__all__ = ["build_page_number_map"]
