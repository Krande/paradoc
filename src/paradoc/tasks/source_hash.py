"""AST source hashing with call-graph walk — Q4 Option C from the design.

The cache key for a task includes a hash of its function body *and* every
Python callable transitively reachable through its body. Solver runs are
minutes; a stale cache from a missed helper-fn change is a correctness
footgun, not just wasted recompute.

What we hash:

- The function's source, parsed to AST then `ast.dump()`-ed. AST
  normalization makes whitespace / comment changes free.
- Every name referenced in the function body, resolved through
  `fn.__globals__` + closure cells. For Python callables (functions,
  classes, methods), recurse into their source. For C-extension
  callables (no `__code__`), fold in the containing module's
  `__version__` (or `__name__` if no version).

What we deliberately don't hash:

- Built-ins, since they're stable across Python minor versions for
  our purposes.
- Names that don't resolve to a callable (eg constants imported for
  use as enum values). Their textual reference is already captured
  by the AST dump.
- Self-references through method calls on parameters
  (`self.attr.method()`) — the type is unknown statically.

Honest scope limits documented in the Q4 design doc:

- Dynamic dispatch (`getattr(obj, name)()`, `globals()[k]()`) is
  invisible to the walker. The `@task(depends_on=[...])` escape hatch
  is for these cases; the cache key folds those hashes too.
- Recursion / cycles are handled by the `_seen` visited set.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from typing import Any, Optional


def ast_source_hash(fn: Any, *, _seen: Optional[set[int]] = None) -> bytes:
    """Hash a callable's source, recursively walking referenced names."""
    if _seen is None:
        _seen = set()
    key = id(fn)
    if key in _seen:
        return b""  # cycle guard
    _seen.add(key)

    h = hashlib.sha256()

    src = _safe_getsource(fn)
    if src is None:
        # No Python source available (C extension, REPL-defined lambda
        # without source, etc.). Fall back to module fingerprint so we
        # at least notice a major-version bump.
        h.update(_module_fingerprint(fn).encode())
        return h.digest()

    try:
        tree = ast.parse(src)
    except SyntaxError:
        # `getsource()` can return source that doesn't reparse cleanly
        # (eg a decorator with arg-less form on a lambda). Fall back to
        # the raw source bytes — still stable across runs, just not
        # AST-normalized.
        h.update(src.encode())
        return h.digest()

    h.update(ast.dump(tree, annotate_fields=False).encode())

    for name_chain in _referenced_names(tree):
        target = _resolve_name_chain(fn, name_chain)
        if target is None or _is_builtin(target):
            continue
        if _is_python_callable(target):
            h.update(ast_source_hash(target, _seen=_seen))
        else:
            h.update(_module_fingerprint(target).encode())

    return h.digest()


def _safe_getsource(fn: Any) -> Optional[str]:
    try:
        # Peel decorators back to the underlying function if @functools.wraps
        # was used. `@task` does this via `functools.update_wrapper`, but the
        # wrapped TaskFn carries `fn` on its instance so we hash that.
        target = getattr(fn, "fn", fn)
        if not callable(target):
            return None
        return inspect.getsource(target)
    except (OSError, TypeError):
        return None


def _referenced_names(tree: ast.AST) -> list[tuple[str, ...]]:
    """Collect every name reference as a tuple of attribute path.

    `helper_fn()` yields `("helper_fn",)`. `mod.sub.fn()` yields
    `("mod", "sub", "fn")`. We collect both `Name` and `Attribute` nodes
    so the resolver can walk module dotted paths.
    """
    chains: list[tuple[str, ...]] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            chains.append((node.id,))
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            chain = _attribute_chain(node)
            if chain is not None:
                chains.append(chain)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return chains


def _attribute_chain(node: ast.Attribute) -> Optional[tuple[str, ...]]:
    """`a.b.c` -> ("a", "b", "c"). Returns None for non-name bases (eg call results)."""
    parts: list[str] = [node.attr]
    cur: ast.AST = node.value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return tuple(reversed(parts))
    return None


def _resolve_name_chain(fn: Any, chain: tuple[str, ...]) -> Any:
    """Walk a name chain through fn.__globals__ + closure -> module attrs."""
    target = getattr(fn, "fn", fn)
    if not chain:
        return None
    head = chain[0]

    obj: Any = _resolve_head(target, head)
    if obj is None:
        return None

    for part in chain[1:]:
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _resolve_head(fn: Any, name: str) -> Any:
    """First name in a chain — check closure, then globals, then builtins."""
    # Closure cells (nested function captures).
    closure = getattr(fn, "__closure__", None)
    code = getattr(fn, "__code__", None)
    if closure and code:
        freevars = getattr(code, "co_freevars", ())
        for var_name, cell in zip(freevars, closure):
            if var_name == name:
                try:
                    return cell.cell_contents
                except ValueError:
                    return None
    globs = getattr(fn, "__globals__", {})
    if name in globs:
        return globs[name]
    # Don't probe __builtins__ — we treat builtins as stable per the
    # design doc, so leaving them unresolved keeps the hash simpler.
    return None


def _is_python_callable(obj: Any) -> bool:
    """True if `obj` has Python source we can hash."""
    return (
        inspect.isfunction(obj)
        or inspect.ismethod(obj)
        or inspect.isclass(obj)
        or hasattr(obj, "fn")  # TaskFn wrapper
    )


def _is_builtin(obj: Any) -> bool:
    """Module-level builtins (print, len, ...) treated as stable."""
    return inspect.isbuiltin(obj)


def _module_fingerprint(obj: Any) -> str:
    """Stable identity proxy for non-Python-callable references.

    Prefer `<module>@<version>`. Fall back to the type's
    qualified name when the object has no module attribute (typical
    of plain dicts / lists / instances). Using `repr(obj)` here would
    embed memory addresses (eg `<function ... at 0x7f1...>`) into the
    hash and make cache keys drift between process invocations — that
    bug was the original motivation for this branch."""
    mod = inspect.getmodule(obj)
    if mod is not None:
        version = getattr(mod, "__version__", None)
        if version:
            return f"{mod.__name__}@{version}"
        return mod.__name__
    # No module → typically an instance. Fingerprint by its *type*
    # path; the textual reference in source AST already covers the
    # value-level identity in practice. For cases that need stricter
    # invalidation, authors use `@task(depends_on=[...])`.
    tp = type(obj)
    return f"<instance:{tp.__module__}.{tp.__qualname__}>"
