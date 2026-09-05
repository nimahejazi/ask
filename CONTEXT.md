# ask

A terminal AI assistant: you ask questions, an LLM answers, optionally executing tools you provide. The notes feature adds durable, user-curated knowledge to that loop.

## Language

### Notes

**Note**:
A single markdown file in `~/.ask-notes/` holding one piece of durable, user-curated knowledge. Its title is the first line; tags are inline `#tag` tokens; the rest is freeform markdown body.
_Avoid_: memo, memory, snippet

**Title**:
The first line of a Note, with leading `#` markers stripped. A Note's identity for display and citation; its filename is derived from it.
_Avoid_: name, heading

**Tag**:
An inline `#tag` token anywhere in a Note's title or body (lowercase, hyphens/underscores allowed). Included in the embedded text so tags nudge semantic search; filterable with `ask notes list --tag`.
_Avoid_: label, category

**Notes Store**:
The directory of Note files — the source of truth. Hand-editable; nothing else in the system may be treated as authoritative over it.
_Avoid_: notes db, notebook

**Notes Index**:
The derived, rebuildable SQLite file at `~/.ask-notes/.index.db` holding Note embeddings and metadata. Disposable: deleting it never loses knowledge; it is rebuilt from the Notes Store.
_Avoid_: notes db, vector db

**Text Search fallback**:
Tag/title/term-overlap ranking used by `search_notes` when no Embedding Provider is available. Keeps notes usable with every provider; a dim notice announces it.
_Avoid_: keyword mode, offline mode

### Assistant integration

**Notes Tools**:
The built-in tools the model may call — `search_notes`, `read_note`, `save_note`. Default-on when notes exist and the provider supports tool calling; `--no-notes` opts out. Deletion is never a tool: AI writes, humans delete.
_Avoid_: memory tools

**Citation**:
The `[note: <title>](<file://path>)` markdown link a Note-backed answer carries, rendered by `rich`. The reference format for answers that drew on a Note.
_Avoid_: attribution, source link

**Embedding Provider**:
The embedding endpoint derived from the configured chat provider (ollama `/api/embed`, LM Studio `/v1/embeddings`, OpenAI for ChatGPT). Anthropic and Mock have none — those fall back to Text Search.
_Avoid_: embedding backend