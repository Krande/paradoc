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

from .wrapper import WordApplication, WordDocument, FigureLayout

__all__ = ['WordApplication', 'WordDocument', 'FigureLayout']
