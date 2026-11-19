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

## Filters made by the build script

A script that builds the document can make filter instances itself (one per analysed object, its values
computed by the script) and register each under its own name:

```python
one = OneDoc("report")
for beam in beams:
    one.add_filter(BeamResults(name=beam.label, beam=beam))
one.compile("report", export_format="pdf")
```

The markdown calls them as any other: `${ b1.utilization:.2f }`. Names must be unique, also against the doc
root's `filters.py` instances.

## Conditional text

Text that fits some objects only goes between condition markers, each an HTML comment on a line of its own:

```markdown
<!-- if b1.slender -->
B1 is slender: its buckling resistance governs.
<!-- else -->
B1 is stocky.
<!-- endif -->
```

The reference is a filter attribute (`name.attr`, called with no arguments) or a document variable (`name`);
`not` negates it, and conditions nest. The value's truth decides, so an attribute returning an empty list of
items drops its branch. A dropped branch is never resolved: its `${ ... }` and figure blocks are not evaluated.
An unknown reference or markers that do not pair up stop the build. Markers inside a fenced code block are text.

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
