# Figure sources

This document demonstrates paradoc's figure-source / filter system.

The substitution syntax is `${ name(.attr)?(args)?(:fmt)? }`. There are
three families of references it covers:

1. **DB-backed tables / plots** — `${ my_table }`, `${ my_plot(width=800) }`
2. **Filter attributes** — `${ eig_main.first_freq:.2f }`
3. **3D figure sources** — declared via `<!-- paradoc:figure ... -->` blocks
   that desugar to filter calls.

The legacy `{{__key__}}{tbl|plt:...}` syntax still works with a
deprecation warning at compile time. Run `paradoc-migrate-syntax
<doc_root>` to rewrite legacy markdown in place.
