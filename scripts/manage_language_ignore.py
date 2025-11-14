"""Utilities for updating the language check ignore list from structured data.

This script accepts JSON data describing new words grouped by subject and category,
applies validation rules, and patches `DEFAULT_IGNORED_WORDS` inside
`src/language_check/language_check_config.py`. Existing entries are preserved and the
output is grouped into comment-delimited blocks.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator, model_validator

from src.scraper import QUALIFICATION_URLS


DEFAULT_CONFIG_PATH = Path("src/language_check/language_check_config.py")
SET_VARIABLE = "DEFAULT_IGNORED_WORDS"
MAX_WORD_LENGTH = 64
ALLOWED_PUNCTUATION = {".", "-", " ", "'", "’", "/"}
VALID_SUBJECT_MAP = {subject.lower(): subject for subject in QUALIFICATION_URLS}
HEADER_RE = re.compile(r"# --- (?P<subject>[^()]+) \((?P<category>[^)]+)\) ---")


def is_allowed_char(char: str) -> bool:
    if char in ALLOWED_PUNCTUATION:
        return True
    category = unicodedata.category(char)
    return category.startswith("L") or category.startswith("N")


@dataclass
class IgnoreEntry:
    subject: str
    category: str
    word: str


@dataclass
class IgnoreBlock:
    subject: str
    category: str
    words: list[str]


class InputWord(BaseModel):
    word: str
    category: str = Field(default="other")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    def accept_misspelled_alias(cls, values: dict[str, object]) -> dict[str, object]:
        if "categogry" in values and "category" not in values:
            values["category"] = values.pop("categogry")
        return values

    @field_validator("word", mode="before")
    def strip_word(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("word")
    def validate_word(cls, value: str) -> str:
        if not value:
            raise ValueError("word must not be empty")
        if len(value) > MAX_WORD_LENGTH:
            raise ValueError(f"word length {len(value)} exceeds limit {MAX_WORD_LENGTH}")
        invalid = {char for char in value if not is_allowed_char(char)}
        if invalid:
            raise ValueError(f"word contains invalid characters: {''.join(sorted(invalid))}")
        return value

    @field_validator("category", mode="before")
    def strip_category(cls, value: object) -> str:
        if value is None:
            return "other"
        text = str(value).strip()
        return text or "other"

    @model_validator(mode="after")
    def enforce_proper_nouns(self) -> "InputWord":
        category = (self.category or "").lower()
        if category == "proper noun" and self.word and not str(self.word)[0].isupper():
            raise ValueError("Proper nouns must start with a capital letter")
        return self


class SubjectBlock(BaseModel):
    subject: str
    words: list[InputWord] = Field(default_factory=list)

    @field_validator("subject", mode="before")
    def trim_subject(cls, value: object) -> str:
        if value is None:
            raise ValueError("subject must not be empty")
        trimmed = str(value).strip()
        if not trimmed:
            raise ValueError("subject must not be empty")
        canonical = VALID_SUBJECT_MAP.get(trimmed.lower())
        if not canonical:
            raise ValueError(
                f"subject '{trimmed}' not recognised (expected one of: {sorted(VALID_SUBJECT_MAP.values())})"
            )
        return canonical


def parse_input(data: Iterable[dict]) -> list[IgnoreEntry]:
    entries: list[IgnoreEntry] = []
    for subject_block in data:
        try:
            validated = SubjectBlock.model_validate(subject_block)
        except ValidationError as exc:
            raise ValueError(f"Invalid subject block {subject_block}: {exc}") from exc
        for word_block in validated.words:
            entries.append(
                IgnoreEntry(subject=validated.subject, category=word_block.category, word=word_block.word)
            )
    return entries


def find_set_bounds(text: str) -> tuple[int, int]:
    match = re.search(rf"{SET_VARIABLE}\s*=\s*{{", text)
    if not match:
        raise ValueError(f"Could not find {SET_VARIABLE} definition in config.")
    brace_level = 0
    start = match.end()
    for idx in range(match.end() - 1, len(text)):
        char = text[idx]
        if char == "{":
            brace_level += 1
        elif char == "}":
            brace_level -= 1
            if brace_level == 0:
                return start, idx
    raise ValueError("Malformed config: unmatched braces.")


def collect_existing_words(text: str) -> set[str]:
    start, end = find_set_bounds(text)
    set_text = text[start:end]
    return set(match.group(1) for match in re.finditer(r'"([^"\n]+?)"', set_text))


def parse_existing_blocks(text: str) -> list[IgnoreBlock]:
    blocks: list[IgnoreBlock] = []
    current: IgnoreBlock | None = None
    for line in text.splitlines():
        stripped = line.strip()
        match = HEADER_RE.match(stripped)
        if match:
            current = IgnoreBlock(subject=match.group("subject"), category=match.group("category"), words=[])
            blocks.append(current)
            continue
        if current and stripped.startswith('"') and stripped.endswith('",'):
            current.words.append(stripped[1:-2])
    return blocks


def insert_block_after_subject(blocks: list[IgnoreBlock], block: IgnoreBlock) -> None:
    for idx in range(len(blocks) - 1, -1, -1):
        if blocks[idx].subject == block.subject:
            blocks.insert(idx + 1, block)
            return
    blocks.append(block)


def merge_new_entries(blocks: list[IgnoreBlock], entries: list[IgnoreEntry]) -> bool:
    block_map = {(block.subject, block.category): block for block in blocks}
    pending_blocks: dict[tuple[str, str], IgnoreBlock] = {}
    pending_order: list[tuple[str, str]] = []
    added = False

    for entry in entries:
        key = (entry.subject, entry.category)
        block = block_map.get(key)
        if block:
            if entry.word not in block.words:
                block.words.append(entry.word)
                added = True
            continue
        pending = pending_blocks.get(key)
        if pending is None:
            pending = IgnoreBlock(subject=entry.subject, category=entry.category, words=[])
            pending_blocks[key] = pending
            pending_order.append(key)
        if entry.word not in pending.words:
            pending.words.append(entry.word)
            added = True

    for key in pending_order:
        insert_block_after_subject(blocks, pending_blocks[key])

    return added


def format_ignore_blocks(blocks: list[IgnoreBlock]) -> str:
    lines = ["\n"]
    for block in blocks:
        lines.append(f"    # --- {block.subject} ({block.category}) ---\n")
        for word in block.words:
            lines.append(f"    \"{word}\",\n")
        lines.append("\n")
    return "".join(lines)


def format_new_entries_block(entries: list[IgnoreEntry]) -> str:
    if not entries:
        return ""
    groups: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        key = (entry.subject, entry.category)
        groups.setdefault(key, []).append(entry.word)
    lines = ["\n"]
    for (subject, category), words in groups.items():
        lines.append(f"    # --- {subject} ({category}) ---\n")
        for word in words:
            lines.append(f"    \"{word}\",\n")
    return "".join(lines)


def apply_updates(config_path: Path, data_path: Path, *, dry_run: bool) -> None:
    config_text = config_path.read_text()
    existing = collect_existing_words(config_text)
    # MAX_WORD_LENGTH is now fixed at 64 (see top of file)

    input_data = json.loads(data_path.read_text())
    raw_entries = parse_input(input_data)
    new_entries = [entry for entry in raw_entries if entry.word not in existing]
    if not new_entries:
        print("No new words to add.")
        return
    start, end = find_set_bounds(config_text)
    set_text = config_text[start:end]
    blocks = parse_existing_blocks(set_text)
    if not merge_new_entries(blocks, new_entries):
        print("No new words to add.")
        return
    insert_text = format_ignore_blocks(blocks)
    updated = config_text[:end] + insert_text + config_text[end:]
    if dry_run:
        print("Dry run: would add the following block:")
        print(format_new_entries_block(new_entries))
        return
    config_path.write_text(updated)
    print(f"Inserted {len(new_entries)} new words into {config_path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage DEFAULT_IGNORED_WORDS from structured JSON.")
    parser.add_argument("data", type=Path, help="JSON file describing subjects and words to ignore.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to language_check_config.py",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the block that would be inserted.")
    args = parser.parse_args()

    apply_updates(args.config, args.data, dry_run=args.dry_run)


if __name__ == "__main__":
    main()