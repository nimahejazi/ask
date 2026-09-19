"""Notes Tools: the built-in tools the model may call to consult and save notes.

search_notes / read_note / save_note. Deletion is never a tool: AI writes,
humans delete (see CONTEXT.md).
"""
import json
from typing import Any, Dict, List, Tuple

from ask.notes import default_notes_store, NotesStore
from ask.notes_index import NotesIndex

BUILT_IN_TOOL_NAMES = ("search_notes", "read_note", "save_note")

NOTES_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_notes",
        "description": (
            "Search the user's personal notes for knowledge relevant to a query. "
            "Returns matching notes with title, tags, a snippet and the file path. "
            "Call this when the question might relate to something the user has noted down."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in the notes."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_note",
        "description": (
            "Read the full markdown content of one note by its file path "
            "(as returned by search_notes)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path of the note, e.g. 'deploy-checklist.md'."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "save_note",
        "description": (
            "Create a new note, or update an existing note with the same title. "
            "Content is markdown; the first line is the title. Inline #tags anywhere. "
            "Notes cannot be deleted via tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title."},
                "content": {"type": "string", "description": "Markdown body (first line becomes the title)."},
            },
            "required": ["title", "content"],
        },
    },
]

_CITE_EXAMPLE = "[note: Deploy Checklist](file:///home/u/.ask-notes/deploy-checklist.md)"


def notes_system_guidance() -> str:
    """Appended to the system prompt when Notes Tools are attached: tells the
    model when to consult notes and how to cite them."""
    return (
        "## Notes\n\n"
        "The user keeps personal notes. When a question might relate to something "
        "the user has noted down, call search_notes first, then read_note on any "
        "promising result before answering.\n\n"
        "When an answer draws on a note, cite it inline as a markdown link like: "
        f"{_CITE_EXAMPLE} — using the note's actual title and file path.\n\n"
        "save_note creates a note or updates an existing note with the same title "
        "(the file path is kept). Only save when the user asks you to remember or "
        "save something. Notes cannot be deleted via tools; tell the user to use "
        "`ask notes delete` instead."
    )


def notes_only_guidance() -> str:
    """Appended when --notes-only: the model must answer exclusively from notes."""
    return (
        "## Notes-only mode\n\n"
        "Answer ONLY from the user's personal notes. Before answering, call "
        "search_notes, then read_note on any promising result. Never use general "
        "knowledge: if no note is relevant or does not contain the answer, say so "
        "and stop.\n\n"
        "When an answer draws on a note, cite it inline as a markdown link like: "
        f"{_CITE_EXAMPLE} — using the note's actual title and file path."
    )


def filter_built_in_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop user tool definitions whose names collide with built-in Notes Tools."""
    return [t for t in tools if t.get("name") not in BUILT_IN_TOOL_NAMES]


def _get_store_and_index(config: Any) -> Tuple[NotesStore, NotesIndex]:
    store = default_notes_store()
    return store, NotesIndex(notes_store=store)


def execute_built_in_tool(
    name: str, args: Dict[str, Any], config: Any = None
) -> Tuple[str, str]:
    """Execute a built-in Notes Tool. Returns (output, error); exactly one is empty."""
    store, index = _get_store_and_index(config)
    provider = config.get("provider", "mock") if config else None

    if name == "search_notes":
        query = str(args.get("query", ""))
        try:
            results = index.search(query, provider=provider, config=config, top_k=5)
        except RuntimeError as e:
            return "", f"Error searching notes: {e}"
        payload = {
            "results": [
                {
                    "title": r.title,
                    "path": r.path.name,
                    "tags": r.note.tags,
                    "snippet": r.snippet,
                    "score": round(r.score, 4),
                }
                for r in results
            ],
            "notice": next((r.notice for r in results if r.notice), ""),
        }
        return json.dumps(payload), ""

    if name == "read_note":
        path_arg = str(args.get("path", ""))
        note = store.find(path_arg)
        if note is None:
            return "", f"Error: note not found: {path_arg}"
        try:
            content = store.read(note.path)
        except (OSError, ValueError) as e:
            return "", f"Error reading note: {e}"
        return json.dumps({"title": note.title, "path": note.path.name, "content": content, "tags": note.tags}), ""

    if name == "save_note":
        title = str(args.get("title", "")).strip()
        content = str(args.get("content", ""))
        if not title or not title_from_first_line(content, title):
            content = f"{title}\n{content}" if content else title
        try:
            path = store.save_note(title=title, content=content)
            # Index the new/changed note right away
            index.sync(provider=provider, config=config)
        except (OSError, ValueError) as e:
            return "", f"Error saving note: {e}"
        return json.dumps({"saved": True, "title": title, "path": path.name}), ""

    return "", f"Error: unknown built-in notes tool: {name}"


def title_from_first_line(content: str, title: str) -> bool:
    """True if the first non-empty line of content already matches the title."""
    for line in content.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s.lower() == title.strip().lower()
    return False