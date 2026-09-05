import json
import time
import pytest
from pathlib import Path

from ask.notes import NotesStore
from ask.notes_index import NotesIndex, TEXT_SEARCH_NOTICE


@pytest.fixture
def store(tmp_path):
    return NotesStore(notes_dir=tmp_path / "notes")


@pytest.fixture
def index(tmp_path, store):
    return NotesIndex(db_path=tmp_path / "index.db", notes_store=store)


def test_sync_embeds_notes_and_search_finds_semantic_match(index, store, monkeypatch):
    store.create("Deploy Checklist\n\nrun kubectl before shipping #ops")
    store.create("Sourdough starter\n\nfeed the starter daily #baking")

    # Fake embeddings: deterministic vectors that make "deploy" related to note 0
    def fake_embed(texts, provider, config):
        out = []
        for t in texts:
            if "deploy" in t.lower() or "checklist" in t.lower():
                out.append([1.0, 0.0, 0.0])
            elif "sourdough" in t.lower() or "starter" in t.lower():
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    monkeypatch.setattr("ask.notes_index.embed_texts", fake_embed)
    index.sync()

    results = index.search("how do I deploy", provider=None, config=None)
    assert [r.path.name for r in results] == ["deploy-checklist.md"]
    assert "deploy" in results[0].snippet.lower()
    assert results[0].embedding_backend == "embedding"


def test_fallback_text_search_when_no_embedding_provider(index, store, monkeypatch):
    store.create("Deploy Checklist\n\nrun kubectl before shipping #ops")
    store.create("Sourdough starter\n\nfeed the starter daily #baking")

    calls = {"n": 0}

    def boom(*a, **kw):
        calls["n"] += 1
        raise RuntimeError("no embedding provider")

    monkeypatch.setattr("ask.notes_index.embed_texts", boom)
    results = index.search("deploy kubectl", provider=None, config=None)
    assert calls["n"] == 1
    assert results[0].path.name == "deploy-checklist.md"
    assert results[0].embedding_backend == "text"
    assert TEXT_SEARCH_NOTICE in results[0].notice


def test_search_ranking_by_term_overlap(index, store, monkeypatch):
    store.create("Alpha\n\nzebra words here")
    store.create("Beta\n\nzebra zebra plains")
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError))
    results = index.search("zebra", provider=None, config=None)
    assert results[0].path.name == "beta.md"
    assert results[0].score > results[1].score


def test_sync_is_lazy_only_changed_files_reembedded(index, store, monkeypatch):
    p1 = store.create("Alpha\nbody alpha")
    p2 = store.create("Beta\nbody beta")

    def fake_embed(texts, provider, config):
        return [[1.0, 0.0], [0.0, 1.0]]

    monkeypatch.setattr("ask.notes_index.embed_texts", fake_embed)
    index.sync()
    assert index.row_count() == 2

    # No file changes -> embed_texts not called again
    calls = {"n": 0}

    def counting_embed(texts, provider, config):
        calls["n"] += 1
        return [[1.0, 0.0], [0.0, 1.0]]

    monkeypatch.setattr("ask.notes_index.embed_texts", counting_embed)
    index.sync()
    assert calls["n"] == 0

    # Touch one file -> only that file re-embedded
    store.update(p1, "Alpha\nchanged body")
    calls2 = {"n": 0}

    def counting_embed2(texts, provider, config):
        calls2["n"] += 1
        assert len(texts) == 1
        return [[0.5, 0.5]]

    monkeypatch.settarget = None
    monkeypatch.setattr("ask.notes_index.embed_texts", counting_embed2)
    index.sync()
    assert calls2["n"] == 1


def test_reindex_forces_full_rebuild(index, store, monkeypatch):
    store.create("Alpha\none")
    store.create("Beta\ntwo")
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: [[1.0], [0.0]])
    index.sync()
    store.update(store.notes_dir / "alpha.md", "Alpha\nchanged")
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: [[0.3, 0.7]])
    index.reindex()
    assert index.row_count() == 2
    assert index.embedded_mtime(store.notes_dir / "alpha.md") is not None


def test_delete_note_removes_index_row(index, store, monkeypatch):
    path = store.create("Alpha\none")
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: [[1.0, 0.0]])
    index.sync()
    assert index.row_count() == 1
    store.delete(path)
    index.sync()
    assert index.row_count() == 0


def test_cosine_similarity():
    from ask.notes_index import _cosine
    assert _cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert _cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert _cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_search_snippet_around_match(index, store, monkeypatch):
    filler = "lorem ipsum " * 200
    store.create("Alpha\n\n%s\nneedle here #tag\n%s" % (filler, filler))
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError))
    results = index.search("needle", provider=None, config=None)
    assert "needle" in results[0].snippet
    assert len(results[0].snippet) <= 260


def test_index_survives_reopen(index, store, monkeypatch, tmp_path):
    store.create("Alpha\none")
    monkeypatch.setattr("ask.notes_index.embed_texts", lambda *a, **k: [[1.0, 0.0]])
    index.sync()
    index2 = NotesIndex(db_path=tmp_path / "index.db", notes_store=store)
    assert index2.row_count() == 1
    results = index2.search("alpha", provider=None, config=None)
    assert results[0].path.name == "alpha.md"