import json
import os
import pathlib
import shutil
import pytest

from ask import cli
from ask.config import Config


@pytest.fixture(autouse=True)
def isolate_home(tmp_path, monkeypatch):
    """Every test runs against a fake home so user files are never touched."""
    home = tmp_path / "isohome"
    home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr("ask.notes.DEFAULT_NOTES_DIR", home / ".ask-notes")
    monkeypatch.setattr("ask.notes_index.DEFAULT_DB_PATH", home / ".ask-notes" / ".index.db")
    yield home


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated environment: config, notes dir, and editor state.

    Path.home patched globally (config, notes store and index all derive from it);
    ask.cli.Config patched so main() reads the isolated config file.
    """
    home = tmp_path / "home"
    home.mkdir()
    notes_dir = home / ".ask-notes"
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr("ask.notes.DEFAULT_NOTES_DIR", notes_dir)
    monkeypatch.setattr("ask.notes_index.DEFAULT_DB_PATH", notes_dir / ".index.db")
    config = Config()
    config._set_path(home / ".askrc")
    monkeypatch.setattr("ask.cli.Config", lambda: config)

    def _write(provider="mock", **extra):
        config.set("provider", provider)
        for k, v in extra.items():
            config.set(k, v)
        return config

    return _write


def _write_config(env, **kw):
    return env(**kw)


def test_notes_subcommand_list_empty(env, capsys):
    _write_config(env)
    rc = cli.main_with_args(["ask", "notes", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "No notes yet" in out


def test_notes_subcommand_add_and_list(env, capsys):
    _write_config(env)
    rc = cli.main_with_args(["ask", "notes", "add", "My note text #tag1"])
    assert rc == 0
    rc = cli.main_with_args(["ask", "notes", "list"])
    out = capsys.readouterr().out
    assert "My note text" in out
    assert "tag1" in out


def test_notes_show_prints_note(env, capsys):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Deploy Checklist\nbody here #ops"])
    rc = cli.main_with_args(["ask", "notes", "show", "deploy-checklist"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "body here" in out


def test_notes_show_missing_exits_nonzero(env, capsys):
    _write_config(env)
    rc = cli.main_with_args(["ask", "notes", "show", "nope"])
    read = capsys.readouterr()
    assert rc == 1
    assert "not found" in (read.err + read.out).lower()


def test_notes_edit_opens_editor(env, capsys, monkeypatch):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Alpha\noriginal"])
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        path = pathlib.Path(cmd[-1])
        path.write_text("Alpha\nedited body")
        return 0

    from pathlib import Path as _P
    monkeypatch.setattr("subprocess.call", fake_run)
    monkeypatch.setenv("EDITOR", "true")
    rc = cli.main_with_args(["ask", "notes", "edit", "alpha"])
    assert rc == 0
    assert calls["cmd"][0] == "true"
    from ask.notes import default_notes_store
    store = default_notes_store()
    assert "edited body" in store.read(store.find_by_title("Alpha").path)


def test_notes_delete_requires_confirmation(env, capsys, monkeypatch):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Alpha\nbody"])
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    rc = cli.main_with_args(["ask", "notes", "delete", "alpha"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Cancelled" in out
    store = cli.default_notes_store() if hasattr(cli, "default_notes_store") else None
    from ask.notes import default_notes_store
    assert default_notes_store().find_by_title("Alpha") is not None


def test_notes_delete_confirmed_removes_note(env, capsys, monkeypatch):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Alpha\nbody"])
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    rc = cli.main_with_args(["ask", "notes", "delete", "alpha"])
    out = capsys.readouterr().out
    assert rc == 0
    from ask.notes import default_notes_store
    assert default_notes_store().find_by_title("Alpha") is None


def test_notes_reindex_reports_count(env, capsys, monkeypatch):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Alpha\none"])
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: [[1.0, 0.0]])
    rc = cli.main_with_args(["ask", "notes", "reindex"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1 note" in out


def test_notes_list_tag_filter(env, capsys):
    _write_config(env)
    cli.main_with_args(["ask", "notes", "add", "Alpha\nbody #ops"])
    cli.main_with_args(["ask", "notes", "add", "Beta\nbody #baking"])
    rc = cli.main_with_args(["ask", "notes", "list", "#ops"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Alpha" in out
    assert "Beta" not in out


def test_query_attaches_notes_tools_by_default(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy Checklist\nkubectl #ops"])
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        captured["system_prompt"] = system_prompt
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "how do I deploy?"])
    assert rc == 0
    names = [t["name"] for t in (captured["tools"] or [])]
    assert "search_notes" in names


def test_no_notes_flag_disables_tools(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy Checklist\nkubectl #ops"])
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "--no-notes", "how do I deploy?"])
    assert rc == 0
    assert captured["tools"] in (None, [])


def test_no_notes_flag_when_no_notes_exist(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "hello"])
    assert rc == 0
    assert captured["tools"] in (None, [])


def test_built_in_tool_execution_search(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy Checklist\nkubectl #ops"])
    from ask.notes_tools import execute_built_in_tool
    output, error = execute_built_in_tool(
        "search_notes", {"query": "deploy"}, config=Config()
    )
    assert error == ""
    assert "Deploy Checklist" in output
    data = json.loads(output)
    assert data["results"][0]["title"] == "Deploy Checklist"


def test_built_in_tool_execution_save(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    from ask.notes_tools import execute_built_in_tool
    output, error = execute_built_in_tool(
        "save_note",
        {"title": "New Note", "content": "New Note\nbody #fromai"},
        config=Config(),
    )
    assert error == ""
    from ask.notes import default_notes_store
    note = default_notes_store().find_by_title("New Note")
    assert note is not None
    data = json.loads(output)
    assert data["saved"] is True


def test_built_in_tool_execution_read(env, capsys):
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Alpha\nsecret body #x"])
    from ask.notes_tools import execute_built_in_tool
    output, error = execute_built_in_tool(
        "read_note", {"path": "alpha.md"}, config=Config()
    )
    assert error == ""
    assert "secret body" in output


def test_built_in_tool_read_path_traversal_blocked(env, capsys):
    _write_config(env, provider="mock")
    from ask.notes_tools import execute_built_in_tool
    output, error = execute_built_in_tool(
        "read_note", {"path": "../secrets.txt"}, config=Config()
    )
    assert error != ""
    assert "not found" in error.lower() or "outside" in error.lower()


def test_ollama_bootstrap_checks_embedding_model(env, capsys, monkeypatch):
    """When configuring ollama, missing embedding model triggers pull prompt."""
    _write_config(env)
    import questionary
    monkeypatch.setattr(
        "ask.cli._select_provider", lambda current=None: "ollama"
    )
    monkeypatch.setattr(
        "ask.cli._select_model", lambda prompt, models, current=None: "llama3"
    )
    monkeypatch.setattr(
        "ask.provider.OllamaProvider.get_available_models",
        classmethod(lambda cls, base_url=None: ["llama3"]),
    )
    # No embedding model present
    monkeypatch.setattr(
        "ask.notes_index.ollama_has_embedding_model",
        lambda base_url=None: False,
    )
    asked = {"n": 0}

    def fake_confirm(prompt, **kw):
        asked["n"] += 1
        return True

    monkeypatch.setattr("questionary.confirm", fake_confirm)
    pulled = {}

    def fake_pull(model):
        pulled["model"] = model
        return True

    # cli.py binds these names via from-import, so patch on ask.cli
    monkeypatch.setattr("ask.cli.ollama_has_embedding_model", lambda base_url=None: False)
    monkeypatch.setattr("ask.cli.ollama_pull_embedding", fake_pull)
    rc = cli.main_with_args(["ask", "-M"])
    out = capsys.readouterr().out
    assert rc == 0
    assert asked["n"] == 1
    assert pulled["model"] == "nomic-embed-text"


def test_ollama_bootstrap_skips_when_embedding_present(env, capsys, monkeypatch):
    _write_config(env)
    monkeypatch.setattr("ask.cli._select_provider", lambda current=None: "ollama")
    monkeypatch.setattr(
        "ask.cli._select_model", lambda prompt, models, current=None: "llama3"
    )
    monkeypatch.setattr(
        "ask.provider.OllamaProvider.get_available_models",
        classmethod(lambda cls, base_url=None: ["llama3", "nomic-embed-text"]),
    )
    monkeypatch.setattr("ask.cli.ollama_has_embedding_model", lambda base_url=None: True)
    monkeypatch.setattr(
        "ask.cli.ollama_pull_embedding", lambda model: (_ for _ in ()).throw(AssertionError("should not pull"))
    )
    rc = cli.main_with_args(["ask", "-M"])
    assert rc == 0


def test_interactive_mode_attaches_notes_tools(env, capsys, monkeypatch):
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Alpha\nbody"])
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    inputs = iter(["how do I deploy?", "exit"])
    monkeypatch.setattr("builtins.input", lambda *a: next(inputs))
    rc = cli.main_with_args(["ask", "--it"])
    assert rc == 0
    names = [t["name"] for t in (captured["tools"] or [])]
    assert "search_notes" in names

def test_notes_help_shows_notes_parser(env, capsys):
    """`ask notes -h` must show the notes help, not the main ask help."""
    rc = cli.main_with_args(["ask", "notes", "-h"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "personal notes" in out.lower()
    assert "browse" in out and "reindex" in out


def test_main_help_mentions_notes(env, capsys):
    rc = cli.main_with_args(["ask", "--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "notes" in out.lower()


def test_notes_subcommand_help(env, capsys):
    rc = cli.main_with_args(["ask", "notes", "add", "--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "EDITOR" in out


def test_notes_add_decodes_newline_escapes(env, capsys):
    """`ask notes add "line one\\nline two"` stores a real newline (title=line one)."""
    _write_config(env)
    rc = cli.main_with_args(["ask", "notes", "add", "line one\\nline two body #ops"])
    assert rc == 0
    from ask.notes import default_notes_store
    store = default_notes_store()
    notes = store.list_notes()
    assert len(notes) == 1
    assert notes[0].title == "line one"
    assert "line two" in notes[0].body
    assert notes[0].path.name == "line-one.md"


def test_notes_add_editor_content_not_escaped_decoded(env, capsys, monkeypatch):
    """$EDITOR path must NOT decode \\n — literal backslash-n there is legitimate."""
    _write_config(env)
    def fake_editor(content, suffix=".md"):
        return "literal\\n stays\\nbackslash"
    monkeypatch.setattr("ask.notes_ui.open_in_editor", fake_editor)
    rc = cli.main_with_args(["ask", "notes", "add"])
    assert rc == 0
    from ask.notes import default_notes_store
    store = default_notes_store()
    note = store.list_notes()[0]
    assert "\\n" in note.content  # literal backslash-n preserved


def test_notes_only_attaches_exactly_notes_tools(env, capsys, monkeypatch):
    """--notes-only attaches exactly the 3 built-in notes tools."""
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy\nrun kubectl first #ops"])
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        captured["system_prompt"] = system_prompt
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "--notes-only", "how do I deploy?"])
    assert rc == 0
    names = sorted(t["name"] for t in (captured["tools"] or []))
    assert names == ["read_note", "save_note", "search_notes"]
    assert "ONLY from the user's personal notes" in captured["system_prompt"]
    assert "Notes-only mode" in captured["system_prompt"]


def test_notes_only_ignores_user_tools_with_warning(env, capsys, monkeypatch, tmp_path):
    """-t alongside --notes-only: user tools dropped, warning printed."""
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy\nrun kubectl first #ops"])
    toolfile = tmp_path / "tools.py"
    toolfile.write_text(
        'TOOLS = [{"name": "user_tool", "description": "d", "parameters": {}}]\n'
    )
    captured = {}

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        captured["tools"] = tools
        return {"content": "answer", "tool_calls": []}

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "--notes-only", "-t", str(toolfile), "q"])
    assert rc == 0
    names = sorted(t["name"] for t in (captured["tools"] or []))
    assert names == ["read_note", "save_note", "search_notes"]
    err = capsys.readouterr().err
    assert "Ignoring -t/--tools" in err


def test_notes_only_mutually_exclusive_with_no_notes(env, capsys):
    _write_config(env, provider="mock")
    rc = cli.main_with_args(["ask", "--no-notes", "--notes-only", "q"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "not allowed with" in err


def test_notes_only_requires_notes(env, capsys):
    """--notes-only with an empty notes store errors cleanly."""
    _write_config(env, provider="mock")
    rc = cli.main_with_args(["ask", "--notes-only", "q"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "No notes found" in err


def test_notes_only_tool_loop_searches(env, capsys, monkeypatch):
    """Under --notes-only the model can call search_notes and get results."""
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy\nrun kubectl first #ops"])
    calls = iter([
        {"content": "", "tool_calls": [{"name": "search_notes", "arguments": {"query": "deploy"}}]},
        {"content": "answer from notes", "tool_calls": []},
    ])

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        return next(calls)

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    monkeypatch.setattr(cli, "execute_built_in_tool", lambda name, args, config=None: (json.dumps({"ok": True}), ""))
    rc = cli.main_with_args(["ask", "--notes-only", "how do I deploy?"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "answer from notes" in out


def test_read_only_note_tools_skip_confirmation(env, capsys, monkeypatch):
    """search_notes/read_note run without prompting; user tools still prompt."""
    _write_config(env, provider="mock")
    cli.main_with_args(["ask", "notes", "add", "Deploy\nkubectl #ops"])
    prompted = []

    def fail_input(prompt=""):
        prompted.append(prompt)
        raise AssertionError("should not prompt for read-only notes tools")

    monkeypatch.setattr("builtins.input", fail_input)
    monkeypatch.setattr("sys.stdin", type("S", (), {"isatty": lambda self: True})())
    rc = cli.main_with_args(["ask", "how do I deploy?"])
    assert rc == 0
    assert prompted == []


def test_save_note_still_prompts(env, capsys, monkeypatch):
    """save_note is a write: it must still ask, and a decline reaches the model."""
    _write_config(env, provider="mock")
    answers = iter(["n"])

    def fake_input(prompt=""):
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("sys.stdin", type("S", (), {"isatty": lambda self: True})())
    calls = iter([
        {"content": "", "tool_calls": [{"name": "save_note", "arguments": {"title": "T", "content": "T\nb"}}]},
        {"content": "noted the decline", "tool_calls": []},
    ])

    def fake_chat(self, query, system_prompt="", history=None, tools=None):
        return next(calls)

    monkeypatch.setattr("ask.provider.MockProvider.chat", fake_chat)
    rc = cli.main_with_args(["ask", "remember this"])
    assert rc == 0
    from ask.notes import default_notes_store
    assert default_notes_store().find_by_title("T") is None
    out = capsys.readouterr().out
    assert "noted the decline" in out
