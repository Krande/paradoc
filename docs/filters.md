# Filter authoring

Filters are the bridge between simulation tasks and the document. They
are user-authored Python classes whose `@attr`-decorated methods are
callable from markdown via `${ instance.attr(args) }`.

## Minimal filter

```python
# <doc_root>/filters.py
from paradoc.filters import Filter, attr

class EigenResults(Filter):
    @attr
    def first_freq(self) -> float:
        return read_first_eigenfrequency_from("results/main.rmed")

eig_main = EigenResults(name="eig_main")
```

Markdown:

```
The first frequency is ${ eig_main.first_freq:.2f } Hz.
```

## Discovery

By default paradoc looks for `<doc_root>/filters.py`. You can override
this in `paradoc.toml`:

```toml
[filters]
modules = ["my_project.filters", "my_project.more_filters"]
```

Every module-level `Filter` instance is registered. We do not auto-
register `Filter` *classes* — only instances. This forces the named-
instance pattern so multiple analyses (e.g. `eig_main` and `eig_alt`)
have unambiguous markdown references.

## Return types

A filter `@attr` may return one of:

- a plain scalar (`int` / `float` / `str` / `bool`) — formatted via the
  optional `:fmt` spec
- `ScalarValue(value=..., units=...)` — explicit wrapper
- `TableView(table_key=..., display_kwargs=...)` — DB-backed table
- `FigureView(plot_key=...)` or `FigureView(image_path=..., caption=...)`
- `ThreeDView(image_path=..., glb_key=..., camera_preset=...)`

The resolver translates the typed view into the right markdown form
(table, figure, or 3D figure with `data-3d-key`).

## Caching

Each `@attr` call is cached by `(filter_name, attr, args, source_hash)`.
The source hash covers only the AST of that specific method, so editing
unrelated methods on the same class does not invalidate the cache.

Persistent caching across builds is a follow-up — today's cache lives
for the duration of one compile.

## Tasks (forward-compat)

Filters can declare an upstream `Task`:

```python
from paradoc.tasks import Task

eig_main = EigenResults(
    name="eig_main",
    task=Task(
        name="simulate_eig",
        inputs=["files/model.inp"],
        outputs=["results/main.rmed"],
        env_lock=Path("env.lock"),
        solver_version="codeaster-15.4",
    ),
)
```

The runtime does not yet execute tasks; the field reservation lets
filter authors model their dependencies today and the future runner
plug in additively.
