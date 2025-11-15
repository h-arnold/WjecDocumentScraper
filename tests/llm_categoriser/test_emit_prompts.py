import os
import sys
from pathlib import Path
from argparse import Namespace

import pytest

# Ensure project root is on sys.path for test imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.document_key import DocumentKey
from src.language_check.language_issue import LanguageIssue


def test_emit_prompts_writes_system_and_user(monkeypatch, tmp_path):
    """Ensure emit_prompts writes a separate system and user file for each batch."""

    # Monkeypatch load_issues to return a single document
    def fake_load(*args, **kwargs):
        key = DocumentKey(subject="TestSubject", filename="test.md")
        return {key: [LanguageIssue(
            filename="test.md",
            rule_id="R1",
            message="msg",
            issue_type="misspelling",
            replacements=[],
            highlighted_context="example",
            issue="example",
            page_number=1,
            issue_id=0,
        )]}

    monkeypatch.setattr("src.llm_review.llm_categoriser.data_loader.load_issues", fake_load)

    # Monkeypatch iter_batches to yield a single Batch object
    from src.llm_review.llm_categoriser.batcher import Batch

    def fake_iter_batches(issues, batch_size, markdown_path, *, subject, filename):
        yield Batch(
            subject=subject,
            filename=filename,
            index=0,
            issues=issues,
            page_context={1: "content"},
            markdown_table="|issue_id|page|rule|message|\n|0|1|R1|msg|\n",
        )

    monkeypatch.setattr("src.llm_review.llm_categoriser.batcher.iter_batches", fake_iter_batches)

    # Ensure build_prompts returns a predictable pair
    def fake_build_prompts(batch):
        return ["SYS_TXT", "USER_TXT"]

    monkeypatch.setattr("src.llm_review.llm_categoriser.prompt_factory.build_prompts", fake_build_prompts)

    # Run emit_prompts with a temp output directory; the function uses
    # data/prompt_payloads by default, so changecwd to tmp_path for safety.
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        from src.llm_review.llm_categoriser.cli import emit_prompts

        args = Namespace(
            from_report=Path("dummy.csv"),
            subjects=None,
            documents=None,
            batch_size=10,
        )

        ret = emit_prompts(args)
        assert ret == 0

        out_dir = Path("data/prompt_payloads")
        system_files = list(out_dir.glob("*system.txt"))
        user_files = list(out_dir.glob("*user.txt"))
        assert system_files, "No system files written"
        assert user_files, "No user files written"

        assert system_files[0].read_text(encoding='utf-8') == "SYS_TXT"
        assert user_files[0].read_text(encoding='utf-8') == "USER_TXT"

    finally:
        os.chdir(cwd)
