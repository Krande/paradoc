# Tables and plots

## DB-backed table reference

The classic case: a table added via `OneDoc.db_manager.add_table()` is
referenced from markdown by its key. Both forms below produce identical
output; the legacy form prints a deprecation warning at compile time.

New (preferred): ${ demo_table }

Legacy alias: {{__demo_table__}}

## With kwargs (annotation flags become Python kwargs)

${ demo_table(no_caption=True) }
