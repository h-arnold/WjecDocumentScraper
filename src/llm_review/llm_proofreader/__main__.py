"""Entry point for running the LLM proofreader as a module."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
