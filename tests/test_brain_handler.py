"""Tests for brain_handler. Mockar filsystem (tmp_path) + subprocess (monkeypatch)."""

import importlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def brain(tmp_path, monkeypatch):
    """Reimport brain_handler with BRAIN_PATH pointing at a fresh tmp dir."""
    monkeypatch.setenv("BRAIN_PATH", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sys.modules.pop("brain_handler", None)
    import brain_handler
    importlib.reload(brain_handler)
    brain_handler._invalidate_context_cache()
    return brain_handler


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# read_brain_context
# ---------------------------------------------------------------------------

def test_read_brain_context_concatenates_files(brain, tmp_path):
    _write(tmp_path / "CLAUDE.md", "rules body")
    _write(tmp_path / "hot-cache.md", "cache body")
    _write(tmp_path / "index.md", "index body")
    out = brain.read_brain_context()
    assert "# CLAUDE.md" in out
    assert "rules body" in out
    assert "# hot-cache.md" in out
    assert "cache body" in out
    assert "# index.md" in out
    assert out.index("CLAUDE.md") < out.index("hot-cache.md") < out.index("index.md")


def test_read_brain_context_caches(brain, tmp_path):
    _write(tmp_path / "CLAUDE.md", "v1")
    _write(tmp_path / "hot-cache.md", "v1")
    _write(tmp_path / "index.md", "v1")
    first = brain.read_brain_context()
    # Mutate file — cache should not invalidate
    (tmp_path / "CLAUDE.md").write_text("v2", encoding="utf-8")
    second = brain.read_brain_context()
    assert first == second
    assert "v2" not in second


def test_read_brain_context_handles_missing_file(brain, tmp_path):
    _write(tmp_path / "CLAUDE.md", "rules")
    _write(tmp_path / "index.md", "index")
    # hot-cache.md saknas
    out = brain.read_brain_context()
    assert "rules" in out
    assert "index" in out


# ---------------------------------------------------------------------------
# fetch_entity
# ---------------------------------------------------------------------------

def test_fetch_entity_scoring_prefers_root_entities_over_clients(brain, tmp_path):
    _write(tmp_path / "entities" / "rasmus.md", "---\ntitle: Rasmus\n---\nfounder")
    _write(
        tmp_path / "entities" / "clients" / "rasmus-testverksamhet-ab.md",
        "---\ntitle: Rasmus Testverksamhet AB\n---\ntestkund",
    )
    out = brain.fetch_entity("Rasmus")
    assert out is not None
    assert "founder" in out
    assert "testkund" not in out


def test_fetch_entity_exact_filename_beats_substring(brain, tmp_path):
    _write(tmp_path / "entities" / "clients" / "foo.md", "exact match body")
    _write(tmp_path / "entities" / "clients" / "foo-corp.md", "substring body")
    out = brain.fetch_entity("foo")
    assert out is not None
    assert "exact match body" in out


def test_fetch_entity_returns_none_on_no_match(brain, tmp_path):
    _write(tmp_path / "entities" / "rasmus.md", "body")
    assert brain.fetch_entity("nonexistent-thing") is None


# ---------------------------------------------------------------------------
# write_session_summary
# ---------------------------------------------------------------------------

def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "README.md").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=path, check=True)


def _mock_anthropic(monkeypatch, summary_text: str = "---\ntitle: Mock\ntype: source\n---\n# Mock\n\nbody"):
    fake_msg = MagicMock()
    fake_msg.text = summary_text
    fake_resp = MagicMock()
    fake_resp.content = [fake_msg]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    fake_anthropic_mod = MagicMock()
    fake_anthropic_mod.Anthropic.return_value = fake_client
    monkeypatch.setattr("brain_handler.anthropic", fake_anthropic_mod)
    return fake_client


def test_write_session_summary_writes_correct_path_and_runs_git(brain, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    _mock_anthropic(monkeypatch)

    git_calls = []
    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):
        git_calls.append(list(cmd))
        # Skip network calls (pull/push)
        if isinstance(cmd, list) and len(cmd) >= 4 and cmd[3] in ("pull", "push"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("brain_handler.subprocess.run", spy_run)

    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hej"}]
    result = brain.write_session_summary(messages, "test-topic")

    assert "error" not in result, result
    assert "discord-" in result["path"]
    assert "test-topic" in result["path"]
    assert Path(result["path"]).exists()

    # Verify commit args contain expected user config + prefix
    commit_calls = [c for c in git_calls if "commit" in c]
    assert commit_calls, f"no commit call in {git_calls}"
    cc = commit_calls[0]
    assert "user.name=gideon-bot" in cc
    assert "user.email=gideon-bot@users.noreply.github.com" in cc
    msg_idx = cc.index("-m") + 1
    assert cc[msg_idx].startswith("ingest: gideon - ")


def test_write_session_summary_filename_collision_suffix(brain, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    _mock_anthropic(monkeypatch)

    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) >= 4 and cmd[3] in ("pull", "push"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("brain_handler.subprocess.run", spy_run)

    messages = [{"role": "user", "content": "hi"}]
    r1 = brain.write_session_summary(messages, "status")
    r2 = brain.write_session_summary(messages, "status")

    assert "error" not in r1 and "error" not in r2
    assert r1["path"] != r2["path"]
    assert r2["path"].endswith("-2.md")


def test_write_session_summary_uses_pull_rebase_not_ff_only(brain, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    _mock_anthropic(monkeypatch)

    git_calls = []
    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):
        git_calls.append(list(cmd))
        if isinstance(cmd, list) and len(cmd) >= 4 and cmd[3] in ("pull", "push"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("brain_handler.subprocess.run", spy_run)

    brain.write_session_summary([{"role": "user", "content": "hi"}], "topic")
    pulls = [c for c in git_calls if "pull" in c]
    assert pulls, "no pull call"
    for p in pulls:
        assert "--rebase" in p
        assert "--ff-only" not in p


def test_write_session_summary_handles_push_failure_gracefully(brain, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    _mock_anthropic(monkeypatch)

    real_run = subprocess.run
    push_call_count = {"n": 0}

    def spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and len(cmd) >= 4:
            if cmd[3] == "push":
                push_call_count["n"] += 1
                raise subprocess.CalledProcessError(1, cmd, output="", stderr="rejected")
            if cmd[3] == "pull":
                return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("brain_handler.subprocess.run", spy_run)

    result = brain.write_session_summary([{"role": "user", "content": "hi"}], "topic")
    assert "error" in result
    assert "git_push" in result["error"]
    # Should retry push exactly once after the first failure
    assert push_call_count["n"] == 2
