"""Tests for the process_all_subjects.py script."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the module we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from process_all_subjects import (
    build_parser,
    commit_changes,
    ensure_branch,
    find_subject_directories,
    git_command,
    main,
    process_subject,
    read_state_file,
    write_state_file,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory structure for testing."""
    # Create Documents directory with subject folders
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir()
    
    (docs_dir / "Art-and-Design").mkdir()
    (docs_dir / "Computer-Science").mkdir()
    (docs_dir / "Geography").mkdir()
    (docs_dir / ".hidden").mkdir()  # Should be ignored
    
    return tmp_path


@pytest.fixture
def state_file(tmp_path):
    """Create a temporary state file."""
    return tmp_path / "unprocessedSubjects.txt"


class TestFindSubjectDirectories:
    """Tests for find_subject_directories function."""
    
    def test_finds_all_directories(self, temp_dir):
        docs_dir = temp_dir / "Documents"
        subjects = find_subject_directories(docs_dir)
        
        assert len(subjects) == 3
        assert "Art-and-Design" in subjects
        assert "Computer-Science" in subjects
        assert "Geography" in subjects
        assert ".hidden" not in subjects  # Hidden dirs should be filtered
    
    def test_returns_sorted_list(self, temp_dir):
        docs_dir = temp_dir / "Documents"
        subjects = find_subject_directories(docs_dir)
        
        assert subjects == sorted(subjects)
    
    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        subjects = find_subject_directories(nonexistent)
        
        assert subjects == []
    
    def test_returns_empty_for_file(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        subjects = find_subject_directories(file_path)
        
        assert subjects == []


class TestStateFile:
    """Tests for state file read/write operations."""
    
    def test_read_empty_state_file(self, state_file):
        subjects = read_state_file(state_file)
        assert subjects == []
    
    def test_write_and_read_state_file(self, state_file):
        subjects = ["Art-and-Design", "Computer-Science", "Geography"]
        write_state_file(state_file, subjects)
        
        read_subjects = read_state_file(state_file)
        assert read_subjects == subjects
    
    def test_write_empty_list(self, state_file):
        write_state_file(state_file, [])
        
        content = state_file.read_text()
        assert content == ""
    
    def test_read_filters_empty_lines(self, state_file):
        state_file.write_text("Art-and-Design\n\nComputer-Science\n\n")
        
        subjects = read_state_file(state_file)
        assert subjects == ["Art-and-Design", "Computer-Science"]
    
    def test_read_strips_whitespace(self, state_file):
        state_file.write_text("  Art-and-Design  \n  Computer-Science  \n")
        
        subjects = read_state_file(state_file)
        assert subjects == ["Art-and-Design", "Computer-Science"]


class TestGitCommand:
    """Tests for git_command function."""
    
    @patch("subprocess.run")
    def test_successful_command(self, mock_run, tmp_path):
        mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")
        
        exit_code, output = git_command(["status"], tmp_path)
        
        assert exit_code == 0
        assert "output" in output
        mock_run.assert_called_once()
    
    @patch("subprocess.run")
    def test_failed_command(self, mock_run, tmp_path):
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        
        exit_code, output = git_command(["invalid"], tmp_path)
        
        assert exit_code == 1
        assert "error" in output
    
    @patch("subprocess.run")
    def test_exception_handling(self, mock_run, tmp_path):
        mock_run.side_effect = Exception("Test exception")
        
        exit_code, output = git_command(["status"], tmp_path)
        
        assert exit_code == 1
        assert "Test exception" in output


class TestEnsureBranch:
    """Tests for ensure_branch function."""
    
    @patch("process_all_subjects.git_command")
    def test_checkout_existing_branch(self, mock_git, tmp_path):
        # First call: branch exists (rev-parse succeeds)
        # Second call: checkout succeeds
        mock_git.side_effect = [
            (0, "commit-sha"),  # rev-parse success
            (0, "Switched to branch"),  # checkout success
        ]
        
        result = ensure_branch("test-branch", tmp_path)
        
        assert result is True
        assert mock_git.call_count == 2
    
    @patch("process_all_subjects.git_command")
    def test_create_new_branch(self, mock_git, tmp_path):
        # First call: branch doesn't exist (rev-parse fails)
        # Second call: create branch succeeds
        mock_git.side_effect = [
            (1, "not found"),  # rev-parse fails
            (0, "Switched to a new branch"),  # checkout -b success
        ]
        
        result = ensure_branch("new-branch", tmp_path)
        
        assert result is True
        assert mock_git.call_count == 2
    
    @patch("process_all_subjects.git_command")
    def test_checkout_failure(self, mock_git, tmp_path):
        mock_git.side_effect = [
            (0, "commit-sha"),  # rev-parse success
            (1, "error"),  # checkout fails
        ]
        
        result = ensure_branch("test-branch", tmp_path)
        
        assert result is False
    
    @patch("process_all_subjects.git_command")
    def test_create_failure(self, mock_git, tmp_path):
        mock_git.side_effect = [
            (1, "not found"),  # rev-parse fails
            (1, "error"),  # checkout -b fails
        ]
        
        result = ensure_branch("new-branch", tmp_path)
        
        assert result is False


class TestCommitChanges:
    """Tests for commit_changes function."""
    
    @patch("process_all_subjects.git_command")
    def test_commit_with_changes(self, mock_git, tmp_path):
        mock_git.side_effect = [
            (0, ""),  # git add success
            (1, ""),  # git diff --cached --quiet (changes exist)
            (0, ""),  # git commit success
        ]
        
        result = commit_changes("Test-Subject", tmp_path)
        
        assert result is True
        assert mock_git.call_count == 3
    
    @patch("process_all_subjects.git_command")
    def test_no_changes_to_commit(self, mock_git, tmp_path):
        mock_git.side_effect = [
            (0, ""),  # git add success
            (0, ""),  # git diff --cached --quiet (no changes)
        ]
        
        result = commit_changes("Test-Subject", tmp_path)
        
        assert result is True
        assert mock_git.call_count == 2  # Should not try to commit
    
    @patch("process_all_subjects.git_command")
    def test_add_failure(self, mock_git, tmp_path):
        mock_git.return_value = (1, "error")
        
        result = commit_changes("Test-Subject", tmp_path)
        
        assert result is False
    
    @patch("process_all_subjects.git_command")
    def test_commit_failure(self, mock_git, tmp_path):
        mock_git.side_effect = [
            (0, ""),  # git add success
            (1, ""),  # git diff --cached --quiet (changes exist)
            (1, "commit error"),  # git commit fails
        ]
        
        result = commit_changes("Test-Subject", tmp_path)
        
        assert result is False


class TestProcessSubject:
    """Tests for process_subject function."""
    
    @patch("subprocess.Popen")
    def test_successful_processing(self, mock_popen, tmp_path):
        # Mock successful subprocess
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["line 1\n", "line 2\n"])
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        
        result = process_subject(
            "Test-Subject",
            tmp_path / "Documents",
            "marker",
            "uv run python",
            tmp_path,
        )
        
        assert result is True
    
    @patch("subprocess.Popen")
    def test_failed_processing(self, mock_popen, tmp_path):
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["error\n"])
        mock_proc.returncode = 1
        mock_popen.return_value = mock_proc
        
        result = process_subject(
            "Test-Subject",
            tmp_path / "Documents",
            "marker",
            "uv run python",
            tmp_path,
        )
        
        assert result is False
    
    @patch("subprocess.Popen")
    def test_exception_during_processing(self, mock_popen, tmp_path):
        mock_popen.side_effect = Exception("Test exception")
        
        result = process_subject(
            "Test-Subject",
            tmp_path / "Documents",
            "marker",
            "uv run python",
            tmp_path,
        )
        
        assert result is False


class TestBuildParser:
    """Tests for argument parser."""
    
    def test_default_arguments(self):
        parser = build_parser()
        args = parser.parse_args([])
        
        assert args.root == Path("Documents")
        assert args.branch == "processedDocuments"
        assert args.state_file == Path("unprocessedSubjects.txt")
        assert args.converter == "marker"
        assert args.uv_cmd == "uv run python"
        assert args.dry_run is False
        assert args.reset is False
    
    def test_custom_arguments(self):
        parser = build_parser()
        args = parser.parse_args([
            "--root", "MyDocs",
            "--branch", "my-branch",
            "--state-file", "state.txt",
            "--converter", "markitdown",
            "--uv-cmd", "python",
            "--dry-run",
            "--reset",
        ])
        
        assert args.root == Path("MyDocs")
        assert args.branch == "my-branch"
        assert args.state_file == Path("state.txt")
        assert args.converter == "markitdown"
        assert args.uv_cmd == "python"
        assert args.dry_run is True
        assert args.reset is True


class TestMainFunction:
    """Integration tests for main function."""
    
    def test_nonexistent_root(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        
        exit_code = main(["--root", str(nonexistent)])
        
        assert exit_code == 2
    
    def test_no_subjects_found(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        exit_code = main(["--root", str(empty_dir)])
        
        assert exit_code == 1
    
    @patch("process_all_subjects.ensure_branch")
    @patch("process_all_subjects.process_subject")
    @patch("process_all_subjects.commit_changes")
    def test_dry_run_mode(self, mock_commit, mock_process, mock_branch, temp_dir):
        state_file = temp_dir / "state.txt"
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
            "--dry-run",
        ])
        
        assert exit_code == 0
        # Should not call branch/process/commit in dry-run
        mock_branch.assert_not_called()
        mock_process.assert_not_called()
        mock_commit.assert_not_called()
    
    @patch("process_all_subjects.ensure_branch")
    @patch("process_all_subjects.process_subject")
    @patch("process_all_subjects.commit_changes")
    def test_successful_processing_flow(self, mock_commit, mock_process, mock_branch, temp_dir):
        mock_branch.return_value = True
        mock_process.return_value = True
        mock_commit.return_value = True
        
        state_file = temp_dir / "state.txt"
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
        ])
        
        assert exit_code == 0
        mock_branch.assert_called_once()
        assert mock_process.call_count == 3  # Three subjects
        assert mock_commit.call_count == 3
        
        # State file should be cleaned up
        assert not state_file.exists()
    
    @patch("process_all_subjects.ensure_branch")
    @patch("process_all_subjects.process_subject")
    @patch("process_all_subjects.commit_changes")
    def test_resume_from_state_file(self, mock_commit, mock_process, mock_branch, temp_dir):
        mock_branch.return_value = True
        mock_process.return_value = True
        mock_commit.return_value = True
        
        state_file = temp_dir / "state.txt"
        # Pre-populate state file with only 2 subjects
        state_file.write_text("Computer-Science\nGeography\n")
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
        ])
        
        assert exit_code == 0
        # Should only process the 2 subjects from state file
        assert mock_process.call_count == 2
    
    @patch("process_all_subjects.ensure_branch")
    def test_branch_creation_failure(self, mock_branch, temp_dir):
        mock_branch.return_value = False
        
        state_file = temp_dir / "state.txt"
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
        ])
        
        assert exit_code == 2
    
    @patch("process_all_subjects.ensure_branch")
    @patch("process_all_subjects.process_subject")
    @patch("process_all_subjects.commit_changes")
    def test_partial_failure(self, mock_commit, mock_process, mock_branch, temp_dir):
        mock_branch.return_value = True
        # First subject succeeds, second fails, third succeeds
        mock_process.side_effect = [True, False, True]
        mock_commit.return_value = True
        
        state_file = temp_dir / "state.txt"
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
        ])
        
        assert exit_code == 2  # Should return error code
        assert mock_process.call_count == 3  # Should continue despite failure
    
    def test_reset_flag(self, temp_dir):
        state_file = temp_dir / "state.txt"
        state_file.write_text("Old-Subject\n")
        
        exit_code = main([
            "--root", str(temp_dir / "Documents"),
            "--state-file", str(state_file),
            "--reset",
            "--dry-run",  # Use dry-run to avoid actual processing
        ])
        
        assert exit_code == 0
        # State file should be recreated with all subjects
        subjects = read_state_file(state_file)
        assert "Art-and-Design" in subjects
        assert "Old-Subject" not in subjects
