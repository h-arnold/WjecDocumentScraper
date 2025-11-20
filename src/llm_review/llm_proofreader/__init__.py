"""LLM Proofreader module.

Provides proofreading functionality for SPELLING_ERROR and ABSOLUTE_GRAMMATICAL_ERROR
issues from the verified categorised language check report.
"""

from .cli import main
from .config import ProofreaderConfiguration
from .runner import ProofreaderRunner

__all__ = [
    "main",
    "ProofreaderConfiguration",
    "ProofreaderRunner",
]
