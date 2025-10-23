"""
Cross-reference and bookmark API for Word documents.

This module provides the public API for working with bookmarks, captions, and cross-references.
Most functionality has been refactored into specialized modules:
- bookmarks.py: Bookmark creation and management
- fields.py: Word field operations (SEQ, REF, STYLEREF)
- captions.py: Caption formatting and rebuilding
- crossref.py: Cross-reference conversion logic
- models.py: Data classes for document references

This file maintains backward compatibility by re-exporting commonly used functions.
"""

# Re-export public API from specialized modules
from .bookmarks import (
    add_bookmark,
    add_bookmark_around_seq_field,
    add_bookmark_to_paragraph as add_bookmark_to_caption,
    add_bookmarkStart,
    normalize_bookmark_name as _normalize_bookmark_name,
)
from .captions import insert_caption, insert_caption_into_runs, rebuild_caption
from .crossref import (
    convert_equation_references_to_ref_fields,
    convert_figure_references_to_ref_fields,
    convert_table_references_to_ref_fields,
    resolve_references,
)
from .fields import (
    add_ref_field_to_paragraph,
    add_seq_reference,
    add_table_reference,
    append_ref_to_paragraph,
)

__all__ = [
    # Bookmarks
    'add_bookmark',
    'add_bookmark_around_seq_field',
    'add_bookmark_to_caption',
    'add_bookmarkStart',
    '_normalize_bookmark_name',
    # Captions
    'insert_caption',
    'insert_caption_into_runs',
    'rebuild_caption',
    # Cross-references
    'convert_equation_references_to_ref_fields',
    'convert_figure_references_to_ref_fields',
    'convert_table_references_to_ref_fields',
    'resolve_references',
    # Fields
    'add_ref_field_to_paragraph',
    'add_seq_reference',
    'add_table_reference',
    'append_ref_to_paragraph',
]

