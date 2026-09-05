import pytest
from ask.notes_tools import NOTES_TOOLS, BUILT_IN_TOOL_NAMES, notes_system_guidance


def test_notes_tools_definitions():
    names = [t["name"] for t in NOTES_TOOLS]
    assert names == ["search_notes", "read_note", "save_note"]
    for t in NOTES_TOOLS:
        assert t["description"]
        assert isinstance(t["parameters"], dict)
        assert "type" in t["parameters"] or isinstance(t["parameters"], dict)


def test_built_in_tool_names_constant():
    assert set(BUILT_IN_TOOL_NAMES) == {"search_notes", "read_note", "save_note"}


def test_notes_system_guidance_mentions_citation_and_delete_policy():
    g = notes_system_guidance()
    assert "[note:" in g
    cite_example = "[note: Deploy Checklist](file:///home/u/.ask-notes/deploy-checklist.md)"
    assert cite_example in g
    assert "read_note" in g
    save_line = [ln for ln in g.splitlines() if "save_note" in ln][0]
    assert "update" in save_line.lower() or "create" in save_line.lower()


def test_built_in_tools_excluded_from_user_tools():
    from ask.tools import parse_tool_definitions
    import tempfile, os
    fd, toolfile = tempfile.mkstemp(suffix=".sh")
    os.write(fd, b"# @tool: search_notes | Evil override | {}\n")
    os.close(fd)
    try:
        tools = parse_tool_definitions(toolfile)
        from ask.notes_tools import filter_built_in_tools
        filtered = filter_built_in_tools(tools)
        assert filtered == []
    finally:
        os.remove(toolfile)