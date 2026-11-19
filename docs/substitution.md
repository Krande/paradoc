# Substitution syntax

Paradoc uses a single substitution syntax to splice computed content
into markdown:

```
${ name (.attr)? (args)? (:fmt)? }
```

| Form                                   | Meaning                                        |
|----------------------------------------|------------------------------------------------|
| `${ my_table }`                        | DB-backed table by key                         |
| `${ my_plot(width=800) }`              | DB-backed plot with display kwargs             |
| `${ eig_main.first_freq:.2f }`         | Filter attribute, scalar with format spec      |
| `${ eig_main.frequency_table }`        | Filter attribute returning a `TableView`       |
| `${ cad_main.view }`                   | Filter attribute returning a `ThreeDView`      |

Format specs are a small safe subset of Python's mini-language:
`.Nf`, `.Ne`, `.Ng`, `d`, `Nd`, `,d`, `,.Nf`, `%`, `.N%`. Anything else
is rejected at compile time.

Argument values must be literals (`str`, `int`, `float`, `bool`, `None`).
Expressions, name lookups, and function calls are not accepted —
substitutions never execute user code.

## Block vs inline placement

A paragraph that contains nothing but a single `${...}` is treated as a
block-level substitution. Inline placement otherwise. This is what lets
the same syntax cover scalar inserts and full-block table / figure
substitution.

## Conditional text

`<!-- if name.attr -->` ... `<!-- else -->` ... `<!-- endif -->` (each on a line of its own, `not` allowed)
keeps the branch the reference's truth says, before any substitution runs. See
[Filter authoring](filters.md#conditional-text).

## Headings

A heading may hold substitutions: `# Beam ${ b1.name } {#sec:b1}`. The web reader letters the appendices from
the first appendix heading as it shows it, i.e. after substitution and without its `{#...}` attributes.

## Migrating from legacy `{{__key__}}` syntax

The previous syntax (`{{__key__}}{tbl:...}` / `{{__key__}}{plt:...}`)
still works with a deprecation warning at compile time. To rewrite a doc
tree in place:

```bash
paradoc-migrate-syntax path/to/doc/
```

The migrator is idempotent — running it twice is a no-op.
