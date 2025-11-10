"""Utility modules for WJEC Document Scraper.

Note: language check modules were moved into the top-level ``src.language_check``
package. This module now only exposes utility submodules that remain under
``src.utils``.
"""

from __future__ import annotations

from . import page_utils

__all__ = [
    "page_utils",
]
