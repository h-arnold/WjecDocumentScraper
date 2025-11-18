import json
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


def test_emit_batch_payloads_writes_system_and_user(monkeypatch, tmp_path):
    """Ensure emit_batch_payloads writes a payload with separate system/user fields."""

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

    monkeypatch.setattr("src.llm_review.core.document_loader.load_issues", fake_load)

    # Monkeypatch iter_batches to yield a single Batch object
    from src.llm_review.core.batcher import Batch

    def fake_iter_batches(issues, batch_size, markdown_path, *, subject, filename):
        yield Batch(
            subject=subject,
            filename=filename,
            index=0,
            issues=issues,
            page_context={1: "content"},
            markdown_table="|issue_id|page|rule|message|\n|0|1|R1|msg|\n",
        )

    monkeypatch.setattr("src.llm_review.core.batcher.iter_batches", fake_iter_batches)

    # Ensure build_prompts returns a predictable pair
    def fake_build_prompts(batch):
        return ["SYS_TXT", "USER_TXT"]

    monkeypatch.setattr("src.llm_review.llm_categoriser.prompt_factory.build_prompts", fake_build_prompts)

    # Run emit_batch_payloads with a temp output directory; the function uses
    # data/batch_payloads by default, so change cwd to tmp_path for safety.
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        from src.llm_review.llm_categoriser.cli import emit_batch_payloads

        args = Namespace(
            from_report=Path("dummy.csv"),
            subjects=None,
            documents=None,
            batch_size=10,
        )

        ret = emit_batch_payloads(args)
        assert ret == 0

        out_dir = Path("data/batch_payloads")
        files = list(out_dir.glob("*.json"))
        assert files, "No payload files written"

        data = json.loads(files[0].read_text(encoding='utf-8'))
        assert data.get("system") == "SYS_TXT"
        assert data.get("user") == ["USER_TXT"]
        # For backward compatibility, original prompts list is still present
        assert data.get("prompts") == ["SYS_TXT", "USER_TXT"]

    finally:
        os.chdir(cwd)