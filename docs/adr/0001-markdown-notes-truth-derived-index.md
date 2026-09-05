# Markdown notes are the source of truth; the vector index is derived and disposable

We decided to give `ask` durable, user-curated knowledge ("notes") that the assistant can consult when answering. We chose **markdown files in `~/.ask-notes/` as the sole source of truth**, with a **derived, rebuildable SQLite index** (`~/.ask-notes/.index.db`) holding embeddings.

Considered options: a single JSON store (matches `~/.askrc` but not hand-editable), one-vector-db-as-store (chroma/lancedb — heavy deps, opaque backups), and sqlite-vec (C-extension risk for no benefit at notes scale). Markdown won because notes are user-curated: users must be able to `vim ~/.ask-notes/*.md`, keep them in git or Dropbox, and never lose knowledge if the index corrupts. The index embeds one vector per note (no chunking) and is rebuilt lazily from file mtimes, or forcibly with `ask notes reindex`. Deleting the index file never loses knowledge.

Consequences: semantic search needs an Embedding Provider derived from the chat provider; where none exists (Anthropic, Mock, LM Studio without an embedding model), `search_notes` falls back to Text Search so notes remain usable everywhere.