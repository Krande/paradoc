"""Paradoc public API.

Heavy compile-time names (`OneDoc`, `Equation`, the docx templates,
`ensure_pandoc_path`) are lazy-loaded via PEP 562 so importers that only
touch the serve path don't drag in pandas / python-docx / pypandoc. The
side-effectful `ensure_pandoc_path()` call now lives next to the modules
that actually invoke pypandoc (see paradoc/document.py).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK
    from .document import OneDoc
    from .equations import Equation
    from .pandoc_helper import ensure_pandoc_path

_LAZY_ATTRS = {
    "MY_DOCX_TMPL": (".common", "MY_DOCX_TMPL"),
    "MY_DOCX_TMPL_BLANK": (".common", "MY_DOCX_TMPL_BLANK"),
    "OneDoc": (".document", "OneDoc"),
    "Equation": (".equations", "Equation"),
    "ensure_pandoc_path": (".pandoc_helper", "ensure_pandoc_path"),
}

__all__ = list(_LAZY_ATTRS)


def __getattr__(name):
    if name in _LAZY_ATTRS:
        module_name, attr = _LAZY_ATTRS[name]
        from importlib import import_module

        value = getattr(import_module(module_name, __name__), attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY_ATTRS))
