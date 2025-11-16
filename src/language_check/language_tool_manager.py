"""LanguageTool setup helpers.

This module centralises LanguageTool instantiation so that dictionary
updates (custom spellings) and shared configuration stay in one place.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Any
import logging

import language_tool_python

# Default LanguageTool server configuration.
#
# The default maxCheckTimeMillis was previously very low (2000 ms) which causes
# the LanguageTool Java server to abort checks on longer documents. That leads
# to connection resets and transient failures when checking large Markdown
# specifications (see: Documents/Spanish/*.md). Bump the timeout so longer
# documents can be processed reliably.
_DEFAULT_CONFIG = {
    "requestLimitPeriodInSeconds": 60,
    # Allow longer checks on large documents without the server aborting.
    # 2 minutes should be sufficient for typical specification files.
    "maxCheckTimeMillis": 120000,
}


class LanguageToolManager:
    """Factory class responsible for configuring LanguageTool instances."""

    def __init__(
        self,
        *,
        ignored_words: Iterable[str] | None = None,
        disabled_rules: Iterable[str] | None = None,
        base_language: str = "en-GB",
        config: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_language = base_language
        self.logger = logger or logging.getLogger(__name__)
        self.config = dict(config) if config is not None else dict(_DEFAULT_CONFIG)
        self.disabled_rules = set(disabled_rules or [])
        self._ignored_words = self._prepare_ignored_words(ignored_words)
        self._spellings_registered = False

    @staticmethod
    def _prepare_ignored_words(words: Iterable[str] | None) -> tuple[str, ...]:
        if not words:
            return tuple()
        deduped: list[str] = []
        seen: set[str] = set()
        for word in words:
            if word is None:
                continue
            cleaned = word.strip()
            if not cleaned or cleaned in seen:
                continue
            deduped.append(cleaned)
            seen.add(cleaned)
        deduped.sort()
        return tuple(deduped)

    def _prepare_new_spellings(self, language: str) -> list[str] | None:
        if not self._ignored_words:
            return None
        if language != self.base_language:
            return None
        if self._spellings_registered:
            return None
        self._spellings_registered = True
        self.logger.info(
            "Registering %d custom spellings with LanguageTool",
            len(self._ignored_words),
        )
        return list(self._ignored_words)

    def build_tool(
        self,
        language: str,
        *,
        extra_disabled_rules: Iterable[str] | None = None,
    ) -> Any:
        """Build a LanguageTool instance for ``language``."""

        kwargs: dict[str, Any] = {}
        if self.config:
            kwargs["config"] = self.config
        new_spellings = self._prepare_new_spellings(language)
        if new_spellings:
            kwargs["newSpellings"] = new_spellings
            kwargs["new_spellings_persist"] = True

        try:
            tool = language_tool_python.LanguageTool(language, **kwargs)
        except TypeError:
            if "config" in kwargs:
                # Older language_tool_python versions do not accept config.
                kwargs.pop("config")
                self.logger.info(
                    "LanguageTool does not accept 'config' — falling back to default constructor",
                )
                tool = language_tool_python.LanguageTool(language, **kwargs)
            else:
                raise

        rules = set(self.disabled_rules)
        if extra_disabled_rules:
            rules.update(extra_disabled_rules)
        if rules:
            try:
                tool.disabled_rules = set(rules)
            except Exception:
                tool.disabled_rules = set(rules)
        return tool

    def build_tools(
        self,
        languages: Sequence[str],
        *,
        extra_disabled_rules: Iterable[str] | None = None,
    ) -> list[Any]:
        """Build LanguageTool instances for each language in ``languages``."""

        return [
            self.build_tool(language, extra_disabled_rules=extra_disabled_rules)
            for language in languages
        ]
