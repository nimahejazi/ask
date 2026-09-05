import os
import shutil
import pytest
from pathlib import Path

from ask.notes import (
    NotesStore,
    parse_tags,
    slugify,
    title_from_content,
)


@pytest.fixture
def store(tmp_path):
    return NotesStore(notes_dir=tmp_path / "notes")


def test_title_from_content_strips_markers_and_blank_lines():
    assert title_from_content("# Deploy Checklist\n\nbody") == "Deploy Checklist"
    assert title_from_content("\n\nMy Note\nbody") == "My Note"
    assert title_from_content("no marker here\nsecond") == "no marker here"


def test_title_from_content_empty_returns_empty():
    assert title_from_content("") == ""
    assert title_from_content("\n  \n") == ""


def test_parse_tags_extracts_inline_tags():
    tags = parse_tags("Deploying the #web_stack with #docker today")
    assert tags == ["web_stack", "docker"]


def test_parse_tags_dedupes_and_excludes_non_tags():
    # "a#b" (no boundary) and bare "#" are not tags; dupes collapse
    assert parse_tags("#a #b #a plain a#b #") == ["a", "b"]


def test_slugify():
    assert slugify("Deploy Checklist!") == "deploy-checklist"
    assert slugify("C++ & Rust notes") == "c-rust-notes"
    assert slugify("  Trimmed   Spaces  ") == "trimmed-spaces"


def test_create_note_writes_file_with_derived_title(store):
    path = store.create("Deploy Checklist\n\n#ops runbook content")
    assert path.parent == store.notes_dir
    assert path.name == "deploy-checklist.md"
    assert path.read_text().startswith("Deploy Checklist")


def test_create_note_slug_collision_gets_suffix(store):
    store.create("Same Title\nbody one")
    path2 = store.create("Same Title\nbody two")
    assert path2.name == "same-title-2.md"


def test_list_notes_returns_sorted_by_updated(store):
    p1 = store.create("Alpha\nfirst")
    p2 = store.create("Beta\nsecond")
    os.utime(p2, (2000000000, 2000000000))
    notes = store.list_notes()
    assert [n.title for n in notes] == ["Beta", "Alpha"]


def test_note_parses_title_tags_body_updated(store):
    store.create("#ops Deploy Checklist\n\nuse #docker always")
    note = store.list_notes()[0]
    assert note.title == "ops Deploy Checklist"
    assert note.tags == ["ops", "docker"]
    assert "always" in note.body
    assert note.updated is not None


def test_read_note_returns_full_content(store):
    path = store.create("Alpha\nthe body")
    assert store.read(path) == "Alpha\nthe body"


def test_read_missing_note_raises(store):
    with pytest.raises(FileNotFoundError):
        store.read(store.notes_dir / "nope.md")


def test_update_note_preserves_path_and_mtime_changes(store):
    path = store.create("Alpha\nold body")
    mtime_before = path.stat().st_mtime
    store.update(path, "Alpha\nnew body")
    assert path.exists()
    assert store.read(path) == "Alpha\nnew body"
    assert path.stat().st_mtime > mtime_before - 1


def test_update_missing_note_raises(store):
    with pytest.raises(FileNotFoundError):
        store.update(store.notes_dir / "nope.md", "text")


def test_delete_note_removes_file(store):
    path = store.create("Alpha\nbody")
    store.delete(path)
    assert not path.exists()


def test_find_by_title_case_insensitive(store):
    store.create("Deploy Checklist\nbody")
    note = store.find_by_title("deploy checklist")
    assert note is not None
    assert note.title == "Deploy Checklist"


def test_find_by_slug(store):
    store.create("Deploy Checklist\nbody")
    note = store.find_by_slug("deploy-checklist")
    assert note is not None


def test_find_missing_returns_none(store):
    assert store.find_by_title("nope") is None
    assert store.find_by_slug("nope") is None


def test_save_note_ai_create(store):
    path = store.save_note(title="New Note", content="New Note\n#ai body")
    assert path.name == "new-note.md"
    assert store.find_by_title("New Note") is not None


def test_save_note_ai_update_existing(store):
    store.create("Existing\nold")
    path = store.save_note(title="Existing", content="Existing\nnew body #updated")
    note = store.find_by_title("Existing")
    assert "new body" in note.body
    assert note.tags == ["updated"]


def test_notes_dir_not_created_on_init_only_on_write(store, tmp_path):
    assert not store.notes_dir.exists()
    store.create("Alpha\nbody")
    assert store.notes_dir.exists()