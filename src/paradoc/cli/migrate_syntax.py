"""`paradoc-migrate-syntax` — rewrite legacy substitution syntax in-place.

Idempotent: running this on already-migrated files is a no-op.
Pairs with the deprecation warning emitted by the legacy `{{__key__}}`
parser at compile time.
"""

from __future__ import annotations

from pathlib import Path

import typer

from paradoc.substitution.migrator import migrate_file, migrate_tree

app = typer.Typer(add_completion=False, help="Migrate legacy substitution syntax to ${...}.")


@app.command()
def migrate(
    root: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True, resolve_path=True),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print summary."),
) -> None:
    """Migrate legacy `{{__key__}}` / `{{ var }}` syntax to `${...}`.

    Operates on a single `.md` file or recursively on a directory. Idempotent.
    """
    if root.is_file():
        results = [migrate_file(root, dry_run=dry_run)]
    else:
        results = migrate_tree(root, dry_run=dry_run)

    total_changed = sum(1 for r in results if r.changed)
    total_replacements = sum(r.replacements for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    if not quiet:
        for r in results:
            if r.changed:
                marker = "[dry-run]" if dry_run else "[migrated]"
                typer.echo(f"{marker} {r.path}: {r.replacements} replacement(s)")
            for w in r.warnings:
                typer.echo(f"  warning: {w}", err=True)

    summary = f"{total_changed}/{len(results)} file(s) changed, {total_replacements} replacement(s)"
    if total_warnings:
        summary += f", {total_warnings} warning(s)"
    if dry_run:
        summary += " (dry run, nothing written)"
    typer.echo(summary)


if __name__ == "__main__":
    app()
