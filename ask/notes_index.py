"""Notes Index: derived, rebuildable SQLite embedding index over the Notes Store.

Markdown files are the source of truth (ADR 0001); this index is disposable.
Embeddings come from the configured chat provider's embedding endpoint; when none
exists, search falls back to Text Search (term-overlap ranking).
"""
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from ask.notes import DEFAULT_NOTES_DIR, NotesStore, Note

DEFAULT_DB_PATH = DEFAULT_NOTES_DIR / ".index.db"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_REQUEST_TIMEOUT = 60

TEXT_SEARCH_NOTICE = "semantic search unavailable — using text search"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes_index (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    embedding TEXT NOT NULL,
    model TEXT,
    title TEXT,
    tags TEXT,
    updated REAL
);
CREATE TABLE IF NOT EXISTS index_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def ollama_has_embedding_model(base_url: str = None) -> bool:
    """Check whether an embedding model is present in the local Ollama library."""
    import requests
    url = f"{(base_url or 'http://localhost:11434').rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        names = [m.get("name", "") for m in response.json().get("models", [])]
    except Exception:
        return False
    for name in names:
        base = name.split(":")[0]
        if "embed" in base.lower():
            return True
    return False


def ollama_pull_embedding(model: str = DEFAULT_EMBEDDING_MODEL) -> bool:
    """Pull the default embedding model into Ollama. Returns success."""
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=600,
        )
        return result.returncode == 0
    except Exception:
        return False


def embed_texts(
    texts: List[str], provider_name: str, config: Any
) -> List[List[float]]:
    """Embed texts via the chat provider's embedding endpoint.

    Raises RuntimeError when no embedding source is available for this provider.
    """
    if not texts:
        return []

    if provider_name == "ollama":
        base_url = (config.get("ollama_base_url", "") or "http://localhost:11434").rstrip("/")
        model = config.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
        payload = {"model": model, "input": texts}
        try:
            import requests
            response = requests.post(f"{base_url}/api/embed", json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if not embeddings or len(embeddings) != len(texts):
                raise RuntimeError(f"Ollama embed returned {len(embeddings or [])} vectors for {len(texts)} texts")
            return [list(map(float, e)) for e in embeddings]
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Ollama embedding failed: {e}")

    if provider_name == "lmstudio":
        base_url = (config.get("lmStudio_base_url", "") or "http://localhost:1234").rstrip("/")
        payload = {"model": "text-embedding-nomic-embed-text-v1.5", "input": texts}
        try:
            import requests
            response = requests.post(f"{base_url}/v1/embeddings", json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            rows = data.get("data", [])
            if len(rows) != len(texts):
                raise RuntimeError(f"LM Studio embed returned {len(rows)} vectors for {len(texts)} texts")
            return [list(map(float, r["embedding"])) for r in rows]
        except Exception as e:
            raise RuntimeError(f"LM Studio embedding failed: {e}")

    if provider_name == "chatgpt":
        api_key = config.get("chatgpt_api_key", "") or __import__("os").getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("No OpenAI API key for embeddings")
        payload = {"model": "text-embedding-3-small", "input": texts}
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        try:
            import requests
            response = requests.post(
                "https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            rows = data.get("data", [])
            if len(rows) != len(texts):
                raise RuntimeError(f"OpenAI embed returned {len(rows)} vectors for {len(texts)} texts")
            rows.sort(key=lambda r: r.get("index", 0))
            return [list(map(float, r["embedding"])) for r in rows]
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {e}")

    raise RuntimeError(f"Provider '{provider_name}' has no embedding endpoint")


def _tokenize(text: str) -> List[str]:
    import re
    return re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower())


def _text_search_score(note: Note, query_tokens: List[str]) -> float:
    """Term-overlap ranking: title hits weigh heavily, tags less, body hits
    accumulate with occurrences."""
    title_tokens = _tokenize(note.title)
    body_tokens = _tokenize(note.body)
    tag_tokens = _tokenize(" ".join(note.tags))
    score = 0.0
    for qt in set(query_tokens):
        if qt in title_tokens:
            score += 3.0
        if qt in tag_tokens:
            score += 2.0
        score += 1.0 * body_tokens.count(qt)
    if not query_tokens:
        return 0.0
    return score / (3.0 * len(set(query_tokens)))


class SearchResult:
    def __init__(self, note: Note, score: float, snippet: str, embedding_backend: str, notice: str = ""):
        self.note = note
        self.path = note.path
        self.title = note.title
        self.score = score
        self.snippet = snippet
        self.embedding_backend = embedding_backend
        self.notice = notice


def _make_snippet(note: Note, query: str, max_len: int = 240) -> str:
    body = note.content
    query_tokens = _tokenize(query)
    best_pos = 0
    for qt in query_tokens:
        idx = body.lower().find(qt)
        if idx > 0:
            best_pos = idx
            break
        elif idx == 0:
            best_pos = 0
            break
    if best_pos > 0:
        start = max(0, best_pos - 80)
        text = body[start:start + max_len]
        prefix = "…" if start > 0 else ""
    else:
        text = body[:max_len]
        prefix = ""
    text = " ".join(text.split())
    return (prefix + text)[:max_len + 1]


class NotesIndex:
    def __init__(self, db_path: Path = None, notes_store: NotesStore = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.store = notes_store or NotesStore()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        return conn

    def sync(self, provider: str = None, config: Any = None) -> Dict[str, int]:
        """Lazily reconcile the index with the Notes Store.

        Embeds new/changed files; drops rows for deleted files. When embedding
        fails, rows are recorded with empty embeddings so Text Search still
        covers them (notice is surfaced by search).
        """
        store = self.store
        notes = store.list_notes()
        conn = self._connect()
        try:
            rows = {
                r[0]: {"path": r[0], "mtime": r[1], "size": r[2]}
                for r in conn.execute("SELECT path, mtime, size FROM notes_index").fetchall()
            }
            db_paths = set(rows.keys())
            fs_paths = {str(n.path.resolve()) for n in notes}

            # Drop deleted
            for gone in db_paths - fs_paths:
                conn.execute("DELETE FROM notes_index WHERE path = ?", (gone,))

            # Determine what needs embedding
            to_embed: List[Note] = []
            for note in notes:
                key = str(note.path.resolve())
                stat = note.path.stat()
                row = rows.get(key)
                if (
                    row is None
                    or row["mtime"] != stat.st_mtime
                    or row["size"] != stat.st_size
                ):
                    to_embed.append(note)

            embedded = 0
            if to_embed:
                # Attempt embeddings unconditionally (provider selects the
                # endpoint; RuntimeError -> Text Search fallback per-note)
                embeddings: List[Optional[List[float]]] = []
                for n in to_embed:
                    tags_line = " ".join(f"#{t}" for t in n.tags)
                    text = f"{n.title}\n{tags_line}\n{n.body}"
                    try:
                        embeddings.append(embed_texts([text], provider, config)[0])
                    except RuntimeError:
                        embeddings.append(None)
                for note, emb in zip(to_embed, embeddings):
                    self._upsert(conn, note, emb)
                    embedded += 1
            conn.commit()
            return {"total": len(notes), "embedded": embedded}
        finally:
            conn.close()

    def _upsert(self, conn, note: Note, embedding: Optional[List[float]]):
        key = str(note.path.resolve())
        conn.execute(
            "INSERT OR REPLACE INTO notes_index (path, mtime, size, embedding, model, title, tags, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                note.path.stat().st_mtime,
                note.path.stat().st_size,
                json.dumps(embedding) if embedding else "[]",
                None,
                note.title,
                json.dumps(note.tags),
                note.updated,
            ),
        )

    def row_count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM notes_index").fetchone()[0]
        finally:
            conn.close()

    def embedded_mtime(self, path: Path) -> Optional[float]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT mtime FROM notes_index WHERE path = ?", (str(path.resolve()),)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def reindex(self, provider: str = None, config: Any = None) -> Dict[str, int]:
        """Force full rebuild: drop everything, re-embed all notes."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM notes_index")
            conn.commit()
        finally:
            conn.close()
        return self.sync(provider=provider, config=config)

    def search(
        self, query: str, provider: str = None, config: Any = None, top_k: int = 5
    ) -> List[SearchResult]:
        """Search notes. Embedding-based when an Embedding Provider exists,
        Text Search fallback otherwise. Each result carries .notice (non-empty
        on the first result when Text Search fallback engaged).

        Does not sync the index; callers (Notes Tools, reindex) own syncing."""
        notes = self.store.list_notes()
        if not notes:
            return []

        query_embedding = None
        try:
            query_embedding = embed_texts([query], provider, config)[0]
        except RuntimeError:
            query_embedding = None

        query_tokens = _tokenize(query)
        scored: List[SearchResult] = []
        backend = "embedding" if query_embedding else "text"
        notice = TEXT_SEARCH_NOTICE if backend == "text" else ""

        conn = self._connect()
        try:
            rows = {
                r[0]: json.loads(r[1])
                for r in conn.execute("SELECT path, embedding FROM notes_index").fetchall()
            }
        finally:
            conn.close()

        for note in notes:
            key = str(note.path.resolve())
            emb = rows.get(key)
            if query_embedding and emb:
                score = _cosine(query_embedding, emb)
            else:
                score = _text_search_score(note, query_tokens)
            if score <= 0:
                continue
            scored.append(
                SearchResult(note, score, _make_snippet(note, query), backend)
            )

        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[:top_k]
        if notice and top:
            top[0].notice = notice
        return top