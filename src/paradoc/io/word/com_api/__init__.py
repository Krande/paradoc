"""COM API wrapper for Word automation.

This module provides a simplified wrapper around the Word COM API (win32com)
for creating and manipulating Word documents with support for:
- Headlines/headings
- Sections
- Figures with captions
- Tables with captions
- Cross-references

The wrapper is only available on Windows platforms.
"""

from .com_utils import is_word_com_available
from .isolated import run_word_operation_isolated
from .wrapper import CaptionReference, FigureLayout, WordApplication, WordDocument

__all__ = [
    "WordApplication",
    "WordDocument",
    "FigureLayout",
    "CaptionReference",
    "run_word_operation_isolated",
    "is_word_com_available",
]
