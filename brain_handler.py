"""Brain handler — Gideons koppling mot axona-brain second-brain vault.

Tre publika funktioner:
    read_brain_context() -> str
    fetch_entity(query) -> Optional[str]
    write_session_summary(messages, topic) -> dict

Vault-katalogen styrs av env var BRAIN_PATH (default /workspace/axona-brain).
Skrivningar går endast till BRAIN_PATH/sources/. Commit-prefix `ingest: gideon -`
filtreras ut av axona-brain GitHub Actions ingest-workflow.
"""

import logging
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

BRAIN_PATH = Path(os.getenv("BRAIN_PATH", "/workspace/axona-brain"))
SUMMARY_MODEL = "claude-sonnet-4-6"
GIT_USER_NAME = "gideon-bot"
GIT_USER_EMAIL = "gideon-bot@users.noreply.github.com"

_CONTEXT_TTL = 1800  # 30 min
_context_cache = {"value": None, "ts": 0.0}


# ---------------------------------------------------------------------------
# read_brain_context
# ---------------------------------------------------------------------------

def _read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("brain file missing: %s", path)
        return ""
    except Exception as e:
        logger.warning("brain file unreadable %s: %s", path, e)
        return ""


def _build_context() -> str:
    parts = []
    for fname in ("CLAUDE.md", "hot-cache.md", "index.md"):
        body = _read_file_safe(BRAIN_PATH / fname)
        if body:
            parts.append(f"# {fname}\n\n{body}")
    return "\n\n".join(parts)


def read_brain_context() -> str:
    """Returnerar CLAUDE.md + hot-cache.md + index.md, cachat 30 min."""
    now = time.time()
    if _context_cache["value"] is not None and now - _context_cache["ts"] < _CONTEXT_TTL:
        return _context_cache["value"]
    value = _build_context()
    _context_cache["value"] = value
    _context_cache["ts"] = now
    return value


def _invalidate_context_cache() -> None:
    _context_cache["value"] = None
    _context_cache["ts"] = 0.0


# ---------------------------------------------------------------------------
# fetch_entity
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


def _extract_frontmatter_title(content: str) -> Optional[str]:
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    fm = content[3:end]
    for line in fm.splitlines():
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


_FOLDER_PRIORITY = {
    "entities": 4,
    "entities/clients": 3,
    "concepts": 2,
    "analyses": 1,
}


def _folder_rank(path: Path) -> int:
    rel = path.relative_to(BRAIN_PATH).as_posix()
    if rel.startswith("entities/clients/"):
        return _FOLDER_PRIORITY["entities/clients"]
    if rel.startswith("entities/"):
        return _FOLDER_PRIORITY["entities"]
    if rel.startswith("concepts/"):
        return _FOLDER_PRIORITY["concepts"]
    if rel.startswith("analyses/"):
        return _FOLDER_PRIORITY["analyses"]
    return 0


def _score_file(path: Path, query: str, query_slug: str) -> int:
    stem = path.stem.lower()
    if stem == query_slug:
        return 100
    content = _read_file_safe(path)
    title = _extract_frontmatter_title(content)
    if title and title.lower() == query.lower():
        return 90
    score = 0
    if query_slug and query_slug in stem:
        score = max(score, 50)
    if title and query.lower() in title.lower():
        score = max(score, 40)
    return score


def fetch_entity(query: str) -> Optional[str]:
    """Sök i entities/, entities/clients/, concepts/, analyses/ med scoring + tie-break."""
    if not query or not BRAIN_PATH.exists():
        return None

    query_slug = _slugify(query)
    candidates = []

    for folder in ("entities", "concepts", "analyses"):
        root = BRAIN_PATH / folder
        if not root.exists():
            continue
        for md in root.rglob("*.md"):
            score = _score_file(md, query, query_slug)
            if score > 0:
                candidates.append((score, _folder_rank(md), md))

    if not candidates:
        return None

    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return _read_file_safe(candidates[0][2])


# ---------------------------------------------------------------------------
# write_session_summary
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = """Du sammanfattar en Discord-konversation till en markdown-källfil för
axona-brain second-brain vault.

Output-format (returnera ENBART detta, ingenting annat):

---
title: <kort, beskrivande titel>
type: source
created: {date}
updated: {date}
sources: []
tags: [discord, gideon, <relevanta tags>]
---

# <samma titel>

<200-300 ord summering på svenska. Fokusera på:
- Vad blev bestämt
- Viktiga fakta som dök upp om kunder, projekt, personer
- Öppna frågor / next steps
- Inga ord-för-ord-citat — destillera>
"""


def _conversation_to_text(messages: list) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def _generate_summary(messages: list, topic: str, date: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    system = _SUMMARY_SYSTEM.format(date=date)
    convo_text = _conversation_to_text(messages)
    user = f"Topic: {topic}\n\nConversation:\n{convo_text}"
    resp = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))


def _git(args: list, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(BRAIN_PATH), *args],
        check=check,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _git_commit(message: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-C",
            str(BRAIN_PATH),
            "-c",
            f"user.name={GIT_USER_NAME}",
            "-c",
            f"user.email={GIT_USER_EMAIL}",
            "commit",
            "-m",
            message,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _resolve_filename(slug: str, date_str: str) -> Path:
    base = f"discord-{date_str}-{slug}"
    sources = BRAIN_PATH / "sources"
    candidate = sources / f"{base}.md"
    n = 2
    while candidate.exists():
        candidate = sources / f"{base}-{n}.md"
        n += 1
    return candidate


def write_session_summary(messages: list, topic: str) -> dict:
    """Generera + skriv summering till brain/sources/ och pusha. Returnerar status-dict."""
    if not messages:
        return {"error": "no messages"}

    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = _slugify(topic)[:40] or "untitled-session"

    try:
        summary = _generate_summary(messages, topic, date_str)
    except Exception as e:
        logger.exception("summary generation failed")
        return {"error": f"summary_generation: {e}"}

    try:
        _git(["pull", "--rebase", "origin", "main"])
    except subprocess.CalledProcessError as e:
        logger.warning("initial pull --rebase failed: %s", e.stderr)

    sources_dir = BRAIN_PATH / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    target = _resolve_filename(slug, date_str)
    target.write_text(summary, encoding="utf-8")

    try:
        _git(["add", str(target.relative_to(BRAIN_PATH))])
        _git_commit(f"ingest: gideon - {topic}")
    except subprocess.CalledProcessError as e:
        logger.exception("git add/commit failed")
        return {"error": f"git_commit: {e.stderr.strip() if e.stderr else str(e)}"}

    try:
        _git(["push", "origin", "main"])
    except subprocess.CalledProcessError:
        logger.warning("push failed, retrying after rebase")
        try:
            _git(["pull", "--rebase", "origin", "main"])
            _git(["push", "origin", "main"])
        except subprocess.CalledProcessError as e:
            return {
                "error": f"git_push: {e.stderr.strip() if e.stderr else str(e)}",
                "path": str(target),
            }

    try:
        sha = _git(["rev-parse", "HEAD"]).stdout.strip()
    except subprocess.CalledProcessError:
        sha = "unknown"

    rel = target.relative_to(BRAIN_PATH).as_posix()
    return {
        "path": str(target),
        "commit": sha,
        "url": f"https://github.com/Axona-Digital/axona-brain/blob/main/{rel}",
    }
