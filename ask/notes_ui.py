"""Notes UI: interactive terminal browser and CRUD over the Notes Store.

`ask notes` opens this. Thin layer over NotesStore; questionary menus, rich tables.
"""
import os
import subprocess
import sys
import tempfile


from rich.console import Console

from ask.notes import default_notes_store, NotesStore

console = Console()

ADD_TEMPLATE = """# {title}

{body}
"""


def _get_editor() -> str:
    return os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"


def open_in_editor(content: str = "", suffix: str = ".md") -> str:
    """Open $EDITOR with content; return the edited text. Empty text on abort."""
    editor = _get_editor()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        try:
            rc = subprocess.call([editor, tmp_path])
        except FileNotFoundError:
            console.print(f"[red]Editor '{editor}' not found.[/red]")
            return ""
        if rc != 0:
            return ""
        with open(tmp_path, "r") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def render_note_list(notes):
    from rich.table import Table
    table = Table(title="Notes")
    table.add_column("Title", style="bold")
    table.add_column("Tags", style="cyan")
    table.add_column("Updated", style="dim")
    for n in notes:
        updated = n.updated.strftime("%Y-%m-%d %H:%M") if hasattr(n.updated, "strftime") else str(n.updated)
        table.add_row(n.title, " ".join(f"#{t}" for t in n.tags), updated)
    console.print(table)


def _print_note(note):
    console.print(f"[bold]{note.title}[/bold] [dim]{note.path.name}[/dim]")
    if note.tags:
        console.print(" ".join(f"[cyan]#{t}[/cyan]" for t in note.tags))
    console.print()
    from rich.markdown import Markdown
    body = note.content.split("\n", 1)[1] if "\n" in note.content else ""
    console.print(Markdown(body or "_empty note_", style="default", justify="left"))


def _confirm_delete(title: str) -> bool:
    import questionary
    return questionary.confirm(f"Delete note '{title}'? This cannot be undone.", default=False).ask() or False


def browse(store: NotesStore = None) -> int:
    """Interactive browser: list -> select -> view/edit/delete. Returns exit code."""
    import questionary
    store = store or default_notes_store()

    while True:
        notes = store.list_notes()
        if not notes:
            console.print("[yellow]No notes yet — run [bold]`ask notes add`[/yellow]")
            return 0

        render_note_list(notes)
        choices = [
            questionary.Choice(f"{n.title}  [dim]({n.path.name})[/dim]", value=n)
            for n in notes
        ] + [questionary.Choice("＋ Add new note", value="add")]
        try:
            selected = questionary.select(
                "Select a note (↑/↓, enter to view; Ctrl+C to quit):",
                choices=choices,
            ).ask()
        except (KeyboardInterrupt, EOFError):
            return 0
        if selected is None:
            return 0

        if selected == "add":
            _add_interactive(store)
            continue

        try:
            action = questionary.select(
                f"'{selected.title}' — action:",
                choices=["View", "Edit in $EDITOR", "Delete", "Back to list", "Quit"],
            ).ask()
        except (KeyboardInterrupt, EOFError):
            return 0
        if action is None or action == "Quit":
            return 0
        if action == "Back to list":
            continue
        if action == "View":
            _print_note(selected)
            console.input("[dim]Press Enter to continue…[/dim]")
        elif action == "Edit in $EDITOR":
            content = store.read(selected.path)
            edited = open_in_editor(content)
            if edited and edited != content:
                store.update(selected.path, edited)
                console.print(f"[green]Updated[/green] {selected.path.name}")
            else:
                console.print("[dim]No changes.[/dim]")
                return 0
        elif action == "Delete":
            if _confirm_delete(selected.title):
                store.delete(selected.path)
                console.print(f"[red]Deleted[/red] {selected.path.name}")
            else:
                console.print("[dim]Cancelled — note kept.[/dim]")


def _add_interactive(store: NotesStore):
    content = open_in_editor(ADD_TEMPLATE.format(title="New Note", body=""))
    if not content.strip():
        console.print("[dim]Empty — note not created.[/dim]")
        return
    path = store.create(content)
    console.print(f"[green]Created[/green] {path.name}")


def _decode_shell_escapes(text: str) -> str:
    """Decode literal \\n and \\t written on the command line into real
    newline/tab. Only for one-shot CLI text; $EDITOR content is untouched."""
    return text.replace("\\t", "\t").replace("\\n", "\n")


def cmd_add(store: NotesStore, args_text: str = "") -> int:
    """`ask notes add` — with text creates directly; without opens $EDITOR."""
    if args_text.strip():
        path = store.create(_decode_shell_escapes(args_text))
        console.print(f"[green]Created[/green] {path.name}")
        return 0
    content = open_in_editor(ADD_TEMPLATE.format(title="New Note", body=""))
    if not content.strip():
        console.print("[dim]Empty — note not created.[/dim]")
        return 0
    path = store.create(content)
    console.print(f"[green]Created[/green] {path.name}")
    return 0


def cmd_edit(store: NotesStore, ref: str) -> int:
    note = store.find(ref)
    if note is None:
        from rich.console import Console
        Console(file=sys.stderr).print(f"[red]Note not found: {ref}[/red]")
        return 1
    content = store.read(note.path)
    edited = open_in_editor(content)
    if edited and edited != content:
        store.update(note.path, edited)
        console.print(f"[green]Updated[/green] {note.path.name}")
    else:
        console.print("[dim]No changes.[/dim]")
    return 0


def cmd_delete(store: NotesStore, ref: str, assume_yes: bool = False) -> int:
    note = store.find(ref)
    if note is None:
        from rich.console import Console
        Console(file=sys.stderr).print(f"[red]Note not found: {ref}[/red]")
        return 1
    if not assume_yes:
        try:
            answer = input(f"Delete note '{note.title}'? This cannot be undone. [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer not in ("y", "yes"):
            console.print("Cancelled — note kept.")
            return 0
    store.delete(note.path)
    console.print(f"[red]Deleted[/red] {note.path.name}")
    return 0