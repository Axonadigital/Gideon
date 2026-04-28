"""Brain handler — Gideon's read+write access to the axona-brain vault.

The brain (axona-brain repo) is the central knowledge source for Axona Digital.
Gideon reads it for context (entities/clients, concepts, analyses) and writes
new sources to it when users ask "save this to brain".

Architecture (per analyses/2026-04-28-gideon-mission-control-roadmap.md):
    Second Brain reads. Gideon acts. Mission Control shows.

Brain access is sandboxed to BRAIN_PATH — Gideon cannot read/write outside it.
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pytz


def _slugify(text: str) -> str:
    """Lowercase, replace åäö, strip non-alphanumerics, collapse dashes."""
    text = (text or "").lower()
    text = (
        text.replace("å", "a")
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("é", "e")
    )
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    return text or "untitled"


class BrainHandler:
    """Read+write access to axona-brain vault, sandboxed to BRAIN_PATH."""

    def __init__(self, brain_path: str, auto_pull: bool = True):
        self.path = Path(brain_path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(
                f"BRAIN_PATH does not exist: {self.path}. "
                f"Clone axona-brain to this path or set BRAIN_PATH correctly."
            )
        if not (self.path / "CLAUDE.md").exists():
            raise FileNotFoundError(
                f"BRAIN_PATH exists but no CLAUDE.md found: {self.path}. "
                f"This is not a valid axona-brain checkout."
            )
        self.auto_pull = auto_pull
        self._last_pull = 0
        if auto_pull:
            self._pull_quiet()

    def _safe_path(self, relative: str) -> Path:
        """Resolve a relative path, ensure it stays inside BRAIN_PATH."""
        # Strip leading slashes so absolute paths get treated as relative
        rel = (relative or "").lstrip("/")
        full = (self.path / rel).resolve()
        if not str(full).startswith(str(self.path)):
            raise ValueError(f"Access denied: {relative} resolves outside brain")
        return full

    def _pull_quiet(self) -> None:
        """git pull, swallow failures (offline scenario)."""
        try:
            subprocess.run(
                ["git", "pull", "--quiet", "--rebase"],
                cwd=self.path,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except Exception:
            pass

    # ==================== READ ====================

    def read_claude_md(self) -> str:
        """Return CLAUDE.md (the schema)."""
        return self._safe_path("CLAUDE.md").read_text(encoding="utf-8")

    def read_hot_cache(self) -> str:
        """Return hot-cache.md (last ingest summary + key pages)."""
        try:
            return self._safe_path("hot-cache.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def read_index(self) -> str:
        """Return index.md (navigable index of the vault)."""
        try:
            return self._safe_path("index.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def read_brain_file(self, relative_path: str) -> str:
        """Read any markdown file inside the brain. Returns text."""
        path = self._safe_path(relative_path)
        if not path.exists():
            return f"❌ Hittade inte {relative_path}"
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"❌ Kunde inte läsa {relative_path}: {e}"

    def list_brain(self, directory: str = ".") -> str:
        """List markdown files in a directory inside the brain."""
        path = self._safe_path(directory)
        if not path.exists() or not path.is_dir():
            return f"❌ {directory} är inte en mapp i brain"
        items = []
        for p in sorted(path.iterdir()):
            if p.name.startswith(".") or p.name == "node_modules":
                continue
            prefix = "📁" if p.is_dir() else "📄"
            items.append(f"{prefix} {p.name}")
        return "\n".join(items) if items else "_tom mapp_"

    def search_brain(self, pattern: str, directory: str = ".") -> str:
        """grep -r pattern in brain. Returns first 50 hits."""
        if not pattern.strip():
            return "❌ tom sökning"
        path = self._safe_path(directory)
        try:
            result = subprocess.run(
                ["grep", "-r", "-n", "-l", "--include=*.md", pattern, "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if not files:
                return f"_inga träffar för '{pattern}'_"
            head = files[:50]
            tail = (
                f"\n_… +{len(files) - 50} fler_" if len(files) > 50 else ""
            )
            return "\n".join(head) + tail
        except Exception as e:
            return f"❌ Kunde inte söka: {e}"

    def find_client(self, query: str) -> Optional[str]:
        """Find an entities/clients/* file by fuzzy name match. Returns relative path."""
        q = _slugify(query)
        if not q:
            return None
        clients_dir = self._safe_path("entities/clients")
        if not clients_dir.exists():
            return None
        # Exact slug match first
        exact = clients_dir / f"{q}.md"
        if exact.exists():
            return f"entities/clients/{q}.md"
        # Substring fallback
        candidates = []
        for p in clients_dir.glob("*.md"):
            stem = p.stem
            if q in stem or stem in q:
                candidates.append(stem)
        if not candidates:
            return None
        # Prefer shortest match (most specific)
        best = min(candidates, key=len)
        return f"entities/clients/{best}.md"

    # ==================== WRITE ====================

    def save_to_sources(
        self,
        slug: str,
        title: str,
        body: str,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a new sources/YYYY-MM-DD-discord-<slug>.md and commit it.

        GitHub Actions ingest pipeline will pick it up and propagate to
        entities/concepts/analyses automatically.
        """
        if self.auto_pull:
            self._pull_quiet()

        tz = pytz.timezone("Europe/Stockholm")
        today = datetime.now(tz).strftime("%Y-%m-%d")
        slug_clean = _slugify(slug)
        if not slug_clean:
            return "❌ Ogiltig slug — ange en kort beskrivande titel"

        filename = f"sources/{today}-discord-{slug_clean}.md"
        path = self._safe_path(filename)

        # Avoid clobbering — append a counter if it exists
        n = 2
        while path.exists():
            filename = f"sources/{today}-discord-{slug_clean}-{n}.md"
            path = self._safe_path(filename)
            n += 1

        tag_list = ", ".join(["discord", "ingest", *(tags or [])])
        frontmatter = (
            f"---\n"
            f"title: {title}\n"
            f"type: source\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            f"sources: []\n"
            f"tags: [{tag_list}]\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"Source: Discord-konversation, sparad av Gideon {today}.\n\n"
            f"## Innehåll\n\n"
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")

        commit_ok = self._commit_and_push(
            files=[filename],
            message=f"ingest: discord conversation — {slug_clean} ({today})",
        )
        if not commit_ok:
            return (
                f"⚠️ Sparade {filename} lokalt men kunde inte pusha till GitHub. "
                f"Kontrollera deploy key + nätverk."
            )
        return (
            f"✅ Sparade till brain: `{filename}`. GitHub Actions kör nu ingest, "
            f"entities/concepts/analyses uppdateras inom någon minut."
        )

    def _commit_and_push(self, files: List[str], message: str) -> bool:
        """git add + commit + push. Returns True on success."""
        try:
            subprocess.run(
                ["git", "add", *files],
                cwd=self.path,
                capture_output=True,
                timeout=30,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.path,
                capture_output=True,
                timeout=30,
                check=True,
            )
            subprocess.run(
                ["git", "push", "--quiet"],
                cwd=self.path,
                capture_output=True,
                timeout=60,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False
