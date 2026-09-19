"""Notes Store: markdown files in ~/.ask-notes/ are the source of truth.

See docs/adr/0001-markdown-notes-truth-derived-index.md and CONTEXT.md.
"""
import re
import unicodedata
from pathlib import Path
from typing import List, Optional

DEFAULT_NOTES_DIR = Path.home() / ".ask-notes"

TAG_RE = re.compile(r"(?<![\w#])#([a-zA-Z0-9][\w-]*)")
SLUG_MAX_LEN = 60


def parse_tags(text: str) -> List[str]:
    """Extract inline #tag tokens: lowercase, deduped, order preserved."""
    seen = []
    for match in TAG_RE.finditer(text):
        tag = match.group(1).lower()
        if tag not in seen:
            seen.append(tag)
    return seen


def slugify(title: str) -> str:
    """Filesystem-safe slug: unicode-fold, lowercase, non-alnum -> '-'."""
    text = unicodedata.normalize("NFKD", title)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(text) > SLUG_MAX_LEN:
        text = text[:SLUG_MAX_LEN].rstrip("-")
    return text or "note"


def title_from_content(content: str) -> str:
    """Title is the first non-empty line with leading markdown markers stripped."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.lstrip("#").strip()
    return ""


class Note:
    """A parsed view of one Note file. Path is the identity; fields are derived."""

    def __init__(self, path: Path, content: str, updated: float):
        self.path = path
        self.content = content
        self.updated = updated
        self.title = title_from_content(content)
        self.tags = parse_tags(content)
        body_lines = content.splitlines()
        self.body = "\n".join(body_lines[1:]) if len(body_lines) > 1 else content
        self.slug = path.stem

    @property
    def file_url(self) -> str:
        from urllib.parse import quote
        return "file://" + quote(str(self.path.resolve()))


class NotesStore:
    def __init__(self, notes_dir: Path = None):
        self.notes_dir = Path(notes_dir) if notes_dir else DEFAULT_NOTES_DIR

    def _ensure_dir(self):
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_in_dir(self, path: Path) -> Path:
        resolved = Path(path).resolve()
        notes_root = self.notes_dir.resolve()
        if notes_root not in resolved.parents:
            raise ValueError(f"Path outside notes dir: {path}")
        return resolved

    def create(self, content: str) -> Path:
        """Create a note from raw markdown content. Returns its path."""
        title = title_from_content(content)
        slug = slugify(title)
        path = self._unique_path(slug)
        self._ensure_dir()
        path.write_text(content, encoding="utf-8")
        return path

    def _unique_path(self, slug: str) -> Path:
        path = self.notes_dir / f"{slug}.md"
        n = 2
        while path.exists():
            path = self.notes_dir / f"{slug}-{n}.md"
            n += 1
        return path

    def list_notes(self) -> List[Note]:
        if not self.notes_dir.exists():
            return []
        notes = []
        for f in self.notes_dir.glob("*.md"):
            try:
                stat = f.stat()
                notes.append(Note(f, f.read_text(encoding="utf-8"), stat.st_mtime))
            except OSError:
                continue
        # mtime descending, ties broken by path so ordering is deterministic
        # even when files share a timestamp (coarse mtime granularity)
        notes.sort(key=lambda n: (-n.updated, n.path.name))
        return notes

    def read(self, path: Path) -> str:
        path = self._resolve_in_dir(path)
        return path.read_text(encoding="utf-8")

    def update(self, path: Path, content: str) -> None:
        path = self._resolve_in_dir(path)
        if not path.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        path.write_text(content, encoding="utf-8")

    def delete(self, path: Path) -> None:
        path = self._resolve_in_dir(path)
        if not path.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        path.unlink()

    def find_by_title(self, title: str) -> Optional[Note]:
        target = title.strip().lower()
        for note in self.list_notes():
            if note.title.lower() == target:
                return note
        return None

    def find_by_slug(self, slug: str) -> Optional[Note]:
        slug = slug.strip().lower().removesuffix(".md")
        for note in self.list_notes():
            if note.slug == slug:
                return note
        return None

    def find(self, ref: str) -> Optional[Note]:
        """Resolve a user/model reference: slug, filename, or exact title."""
        return self.find_by_slug(ref) or self.find_by_title(ref)

    def save_note(self, title: str, content: str) -> Path:
        """AI-facing save: create, or overwrite the body of an existing note by title.

        The existing note keeps its path (and any hand-made structure); content replaces
        the body while the note file keeps title as first line.
        """
        existing = self.find_by_title(title)
        if existing:
            new_content = f"{title}\n{content}"
            self.update(existing.path, new_content)
            return existing.path
        return self.create(f"{title}\n{content}")


def default_notes_store() -> NotesStore:
    return NotesStore(DEFAULT_NOTES_DIR)