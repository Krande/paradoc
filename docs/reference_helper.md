# ReferenceHelper: Cross-Reference Management System

## Overview

The `ReferenceHelper` class is a centralized manager for all cross-references (figures, tables, equations) in Word documents. It was created to solve persistent issues with cross-reference conversion in Paradoc's Word export functionality.

## Problem Statement

Based on the investigation in `examples/docx_diagnostics/FINDINGS.md`, the original implementation had several issues:

1. **Figure cross-references were not being converted to REF fields** - while table references worked, figure references remained as plain text
2. **Bookmark management was decentralized** - bookmarks were created ad-hoc during formatting without a unified registry
3. **No reliable mapping between semantic IDs and Word bookmarks** - made it difficult to track which references pointed to which items
4. **Post-processing approach was fragile** - trying to convert references after document creation led to pattern matching failures

## Solution: ReferenceHelper

The `ReferenceHelper` class addresses these issues by:

### 1. Centralized Registry

Maintains a single source of truth for all cross-referenceable items:
- Tracks figures, tables, and equations separately
- Preserves document order across all types
- Maps semantic IDs (e.g., "test_figure") to Word-style bookmarks (e.g., "_Ref306075071")

### 2. Word-Compatible Bookmark Names

Generates bookmark names that match Word's native format:
- Format: `_Ref` + 9-digit random number
- Example: `_Ref306075071`
- Ensures compatibility with Word's cross-reference system

### 3. Registration During Formatting

Items are registered as they are formatted, ensuring accurate tracking:

```python
# In models.py - format_figure()
if reference_helper:
    bookmark_name = reference_helper.register_figure(
        self.figure_ref.reference, 
        self.docx_caption
    )
    self.actual_bookmark_name = bookmark_name
    add_bookmark_around_seq_field(self.docx_caption, bookmark_name)
```

### 4. Intelligent Reference Conversion

After all items are registered and captions are formatted:

```python
# In exporter.py
ref_helper.update_display_numbers()  # Extract numbers from captions
ref_helper.convert_all_references(document)  # Convert text to REF fields
```

The conversion process:
1. Scans caption paragraphs to extract display numbers (e.g., "1-1", "2-3")
2. Builds a mapping of display numbers to bookmarks
3. Finds all text references in the document (e.g., "Figure 1-1")
4. Replaces them with proper REF fields pointing to the correct bookmarks

## Architecture

### Class Structure

```
ReferenceHelper
├── _figures: Dict[str, ReferenceItem]      # Figure registry
├── _tables: Dict[str, ReferenceItem]       # Table registry
├── _equations: Dict[str, ReferenceItem]    # Equation registry
└── _all_items: List[ReferenceItem]         # All items in document order

ReferenceItem
├── ref_type: ReferenceType                 # FIGURE, TABLE, or EQUATION
├── semantic_id: str                        # "test_figure"
├── word_bookmark: str                      # "_Ref306075071"
├── display_number: str                     # "1-1"
├── caption_paragraph: Paragraph            # Actual Word paragraph
└── document_order: int                     # Sequential position
```

### Integration Points

#### 1. WordExporter (`exporter.py`)

```python
def _compile_individual_md_files_to_docx(self, ...):
    # Initialize helper
    ref_helper = ReferenceHelper()
    
    # Pass to formatting methods
    main_tables = self.format_tables(composer_main.doc, False, ref_helper)
    main_figures = self.format_figures(composer_main.doc, False, ref_helper)
    
    # After merging, convert references
    ref_helper.update_display_numbers()
    ref_helper.convert_all_references(composer_main.doc)
```

#### 2. DocXFigureRef (`models.py`)

```python
def format_figure(self, is_appendix, restart_caption_numbering, reference_helper=None):
    # Format caption with SEQ fields
    rebuild_caption(self.docx_caption, "Figure", ...)
    
    # Register with helper and add bookmark
    if reference_helper:
        bookmark_name = reference_helper.register_figure(
            self.figure_ref.reference, 
            self.docx_caption
        )
        add_bookmark_around_seq_field(self.docx_caption, bookmark_name)
```

#### 3. DocXTableRef (`models.py`)

Similar to figures, tables register themselves during formatting.

### Key Methods

#### Registration

- `register_figure(semantic_id, caption_para)` - Register a figure
- `register_table(semantic_id, caption_para)` - Register a table
- `register_equation(semantic_id, caption_para)` - Register an equation

#### Retrieval

- `get_figure_bookmark(semantic_id)` - Get Word bookmark for a figure
- `get_all_figure_bookmarks_in_order()` - Get all figure bookmarks in document order
- Similar methods for tables and equations

#### Conversion

- `update_display_numbers()` - Extract display numbers from caption paragraphs
- `convert_all_references(document)` - Convert all text references to REF fields

## Benefits

### 1. Reliability

- **Guaranteed bookmark creation**: Every registered item gets a bookmark
- **Consistent naming**: All bookmarks follow Word's convention
- **Order preservation**: Document order is maintained across all types

### 2. Maintainability

- **Single source of truth**: All cross-reference logic in one place
- **Clear separation of concerns**: Registration vs. conversion
- **Easy debugging**: `print_registry()` shows complete state

### 3. Extensibility

- **Easy to add new types**: Just add a new registry and methods
- **Flexible conversion**: Pattern matching can be customized
- **Backward compatible**: Falls back to old method if no helper provided

## Usage Example

```python
from paradoc.io.word.reference_helper import ReferenceHelper

# Initialize
helper = ReferenceHelper()

# Register items as you format them
fig1_bookmark = helper.register_figure("intro_chart", figure_caption_para)
tbl1_bookmark = helper.register_table("results", table_caption_para)

# After all formatting is complete
helper.update_display_numbers()
helper.convert_all_references(document)

# Debug if needed
helper.print_registry()
```

## Migration from Old System

### Old Approach (crossref.py)

```python
# Post-processing approach
convert_figure_references_to_ref_fields(doc, all_figures)
convert_table_references_to_ref_fields(doc, all_tables)

# Issues:
# - Fragile pattern matching
# - No centralized registry
# - Hard to track what went wrong
```

### New Approach (reference_helper.py)

```python
# Registration during formatting
ref_helper = ReferenceHelper()
for figure in figures:
    figure.format_figure(..., reference_helper=ref_helper)

# Conversion after all items registered
ref_helper.update_display_numbers()
ref_helper.convert_all_references(doc)

# Benefits:
# - Reliable mapping
# - Centralized state
# - Easy debugging
```

## Testing

Comprehensive unit tests in `tests/docx_cross/test_reference_helper.py`:

- Registration of figures, tables, equations
- Bookmark uniqueness and format
- Document order preservation
- Display number extraction
- Reference conversion logic

Run tests:
```bash
pixi run -e test python -m pytest tests/docx_cross/test_reference_helper.py -v
```

## Future Enhancements

1. **Equation support**: Add full equation cross-reference support
2. **Custom bookmark names**: Allow user-specified bookmark names
3. **Reference validation**: Detect broken references before export
4. **Performance optimization**: Batch processing for large documents
5. **Style preservation**: Maintain text formatting in REF fields

## Related Files

- `src/paradoc/io/word/reference_helper.py` - Main implementation
- `src/paradoc/io/word/exporter.py` - Integration in WordExporter
- `src/paradoc/io/word/models.py` - Integration in DocXFigureRef and DocXTableRef
- `src/paradoc/io/word/bookmarks.py` - Bookmark creation utilities
- `src/paradoc/io/word/fields.py` - REF field creation utilities
- `tests/docx_cross/test_reference_helper.py` - Unit tests
- `examples/docx_diagnostics/FINDINGS.md` - Original problem analysis

## Conclusion

The `ReferenceHelper` class provides a robust, maintainable solution to cross-reference management in Paradoc's Word export system. By centralizing registration and conversion logic, it ensures that all figures, tables, and equations have proper Word-compatible bookmarks and that all text references are correctly converted to REF fields.

