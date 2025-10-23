# Word COM API Wrapper

A simplified wrapper around the Word COM API (win32com) for creating and manipulating Word documents programmatically.

## Overview

This module provides high-level Python classes that simplify working with Microsoft Word through COM automation. It abstracts away the complexity of the raw COM API and provides an intuitive, Pythonic interface for common document operations.

**Note:** This module is only available on Windows platforms and requires Microsoft Word to be installed.

## Features

- **Document Management**: Create and open Word documents
- **Content Creation**: Add headings, paragraphs, sections
- **Figures**: Insert images or placeholder shapes with automatic numbering and captions
- **Tables**: Create tables with automatic numbering and captions
- **Cross-References**: Link to figures and tables with automatic updating
- **Sections & Breaks**: Add page breaks and section breaks
- **Context Manager**: Safe cleanup of Word instances

## Installation

Requires the `pywin32` package:

```bash
pip install pywin32
```

## Quick Start

```python
from paradoc.io.word.com_api import WordApplication

# Create a document using context manager (recommended)
with WordApplication(visible=False) as word_app:
    doc = word_app.create_document()
    
    # Add content
    doc.add_heading("My Document", level=1)
    doc.add_paragraph("This is a paragraph.")
    
    # Add a figure with caption
    doc.add_figure_with_caption("Example figure description")
    
    # Add a table with caption
    doc.add_table_with_caption("Example table", rows=3, cols=3)
    
    # Add a cross-reference to the first figure
    doc.add_cross_reference("figure_0", reference_type="figure", prefix_text="See ")
    
    # Update fields and save
    doc.update_fields()
    doc.save("output.docx")
```

## Using Templates

You can create documents based on a template .docx file. This allows you to use predefined styles, formatting, headers, footers, and other settings from the template:

```python
from paradoc.io.word.com_api import WordApplication

with WordApplication(visible=False) as word_app:
    # Create a document based on a template
    doc = word_app.create_document(template="my_template.docx")
    
    # Add content - styles from template will be used
    doc.add_heading("Report Title", level=1)  # Uses "Heading 1" style from template
    doc.add_paragraph("Introduction text.")    # Uses "Normal" style from template
    
    # All other functionality works the same
    doc.add_figure_with_caption("Data visualization")
    doc.save("output.docx")
```

The template document should be a valid .docx file with the styles and formatting you want to use. When creating a document from a template:
- All styles defined in the template are available
- Default fonts and formatting are inherited from the template
- Headers, footers, and page setup are copied from the template
- The template file itself remains unchanged

## API Reference

### WordApplication

Main class for managing the Word application instance.

#### Constructor

```python
WordApplication(visible=False)
```

- `visible` (bool): Whether to show the Word application window

#### Methods

- `start()`: Start the Word application
- `quit()`: Quit the Word application and close all documents
- `create_document(template=None)`: Create a new Word document (returns `WordDocument`)
  - `template` (str or Path, optional): Path to a template .docx file to base the document on
- `open_document(path)`: Open an existing Word document (returns `WordDocument`)

#### Context Manager

```python
with WordApplication(visible=False) as word_app:
    # Work with Word
    pass
# Word automatically quits when exiting the context
```

### WordDocument

Wrapper for a Word document with high-level content manipulation methods.

#### Content Methods

##### add_heading(text, level=1)

Add a heading to the document.

- `text` (str): The heading text
- `level` (int): The heading level (1-9, where 1 is "Heading 1")

```python
doc.add_heading("Chapter 1", level=1)
doc.add_heading("Section 1.1", level=2)
```

##### add_paragraph(text="", style="Normal")

Add a paragraph to the document.

- `text` (str): The paragraph text (optional)
- `style` (str): The paragraph style (default: "Normal")

```python
doc.add_paragraph("This is a paragraph.")
doc.add_paragraph()  # Empty paragraph for spacing
```

##### add_page_break()

Insert a page break.

```python
doc.add_page_break()
```

##### add_section_break(break_type="next_page")

Insert a section break.

- `break_type` (str): Type of section break:
  - `"next_page"`: Start on next page (default)
  - `"continuous"`: Continue on same page
  - `"even_page"`: Start on next even page
  - `"odd_page"`: Start on next odd page

```python
doc.add_section_break("next_page")
```

#### Figure Methods

##### add_figure_with_caption(caption_text, image_path=None, width=None, height=None, layout=FigureLayout.INLINE, create_bookmark=True, use_chapter_numbers=False)

Add a figure with a caption using Word's SEQ field for automatic numbering.

- `caption_text` (str): The caption text (without "Figure X:" prefix)
- `image_path` (str | Path): Optional path to image file to insert
- `width` (float): Optional width for image/shape in points
- `height` (float): Optional height for image/shape in points
- `layout` (FigureLayout | str): Layout/text wrapping style for the figure. Options:
  - `FigureLayout.INLINE` or `"inline"`: Inline with text (default)
  - `FigureLayout.SQUARE` or `"square"`: Square wrapping around the figure
  - `FigureLayout.TIGHT` or `"tight"`: Tight wrapping following figure outline
  - `FigureLayout.THROUGH` or `"through"`: Text wraps through transparent areas
  - `FigureLayout.TOP_BOTTOM` or `"top_bottom"`: Text above and below only
  - `FigureLayout.BEHIND_TEXT` or `"behind_text"`: Figure behind text
  - `FigureLayout.IN_FRONT_OF_TEXT` or `"in_front_of_text"`: Figure in front of text
- `create_bookmark` (bool): Whether to create a bookmark for cross-referencing
- `use_chapter_numbers` (bool): Whether to use chapter-based numbering (e.g., 1.1, 1.2, 2.1). Requires Heading 1 styles in the document. Default is False (simple numbering: 1, 2, 3, etc.)

Returns: The bookmark name if `create_bookmark=True`, otherwise `None`

```python
from paradoc.io.word.com_api import WordApplication, FigureLayout

# Add a figure with an image (default inline layout)
fig_bookmark = doc.add_figure_with_caption(
    caption_text="System Architecture",
    image_path="diagram.png",
    width=400,
    height=300
)

# Add a figure placeholder (no image)
fig_bookmark = doc.add_figure_with_caption("Placeholder Figure")

# Add a figure with square text wrapping
fig_bookmark = doc.add_figure_with_caption(
    caption_text="Wrapped Figure",
    image_path="chart.png",
    layout=FigureLayout.SQUARE
)

# Add a figure with tight text wrapping (using string)
fig_bookmark = doc.add_figure_with_caption(
    caption_text="Tight Wrapped Figure",
    image_path="photo.png",
    layout="tight"
)

# Add a figure behind text (watermark-style)
fig_bookmark = doc.add_figure_with_caption(
    caption_text="Background Figure",
    image_path="logo.png",
    layout=FigureLayout.BEHIND_TEXT
)

# Chapter-based numbering (e.g., 1.1, 1.2, 2.1, 2.2)
# Requires Heading 1 styles in the document
doc.add_heading("Chapter 1: Introduction", level=1)
doc.add_figure_with_caption(
    caption_text="First figure in chapter 1",
    use_chapter_numbers=True  # Will be numbered as Figure 1.1
)
doc.add_figure_with_caption(
    caption_text="Second figure in chapter 1",
    use_chapter_numbers=True  # Will be numbered as Figure 1.2
)

doc.add_heading("Chapter 2: Methods", level=1)
doc.add_figure_with_caption(
    caption_text="First figure in chapter 2",
    use_chapter_numbers=True  # Will be numbered as Figure 2.1
)
```

#### Table Methods

##### add_table_with_caption(caption_text, rows=2, cols=2, data=None, create_bookmark=True, use_chapter_numbers=False)

Add a table with a caption using Word's SEQ field for automatic numbering.

- `caption_text` (str): The caption text (without "Table X:" prefix)
- `rows` (int): Number of rows in the table
- `cols` (int): Number of columns in the table
- `data` (list[list], optional): Data to populate the table. Should be a list of lists where each inner list represents a row. If provided, dimensions must match the table size (rows x cols). Values will be converted to strings.
- `create_bookmark` (bool): Whether to create a bookmark for cross-referencing
- `use_chapter_numbers` (bool): Whether to use chapter-based numbering (e.g., 1.1, 1.2, 2.1). Requires Heading 1 styles in the document. Default is False (simple numbering: 1, 2, 3, etc.)

Returns: The bookmark name if `create_bookmark=True`, otherwise `None`

```python
# Empty table
table_bookmark = doc.add_table_with_caption(
    caption_text="Results Summary",
    rows=5,
    cols=4
)

# Table with data
data = [
    ["Name", "Age", "City"],
    ["Alice", "30", "New York"],
    ["Bob", "25", "London"],
]
table_bookmark = doc.add_table_with_caption(
    caption_text="User Data",
    rows=3,
    cols=3,
    data=data
)

# Table with mixed data types (automatically converted to strings)
numeric_data = [
    ["Item", "Quantity", "Price"],
    ["Apple", 10, 1.50],
    ["Banana", 20, 0.75],
]
doc.add_table_with_caption(
    caption_text="Inventory",
    rows=3,
    cols=3,
    data=numeric_data
)

# Chapter-based numbering (e.g., 1.1, 1.2, 2.1, 2.2)
# Requires Heading 1 styles in the document
doc.add_heading("Chapter 1: Introduction", level=1)
doc.add_table_with_caption(
    caption_text="First table in chapter 1",
    rows=2,
    cols=2,
    use_chapter_numbers=True  # Will be numbered as Table 1.1
)
doc.add_table_with_caption(
    caption_text="Second table in chapter 1",
    rows=2,
    cols=2,
    use_chapter_numbers=True  # Will be numbered as Table 1.2
)

doc.add_heading("Chapter 2: Methods", level=1)
doc.add_table_with_caption(
    caption_text="First table in chapter 2",
    rows=2,
    cols=2,
    use_chapter_numbers=True  # Will be numbered as Table 2.1
)
```

#### Cross-Reference Methods

##### add_cross_reference(bookmark_name, reference_type="figure", include_hyperlink=True, prefix_text="")

Add a cross-reference to a figure or table.

- `bookmark_name` (str | int): The bookmark name or index (e.g., "figure_0" or 0)
- `reference_type` (str): Type of reference ("figure" or "table")
- `include_hyperlink` (bool): Whether to make the reference a clickable hyperlink
- `prefix_text` (str): Optional text to insert before the reference (e.g., "See ")

```python
# Reference the first figure
doc.add_cross_reference("figure_0", reference_type="figure", prefix_text="See ")

# Reference by index
doc.add_cross_reference(0, reference_type="table", prefix_text="Refer to ")
```

#### Document Management Methods

##### update_fields()

Update all fields in the document (important for SEQ fields to show correct numbers).

```python
doc.update_fields()
```

##### save(path)

Save the document.

- `path` (str | Path): Path where to save the document

```python
doc.save("output.docx")
```

##### close(save_changes=False)

Close the document.

- `save_changes` (bool): Whether to save changes before closing

```python
doc.close(save_changes=False)
```

##### get_bookmark_names()

Get all bookmark names in the document.

Returns: List of bookmark names

```python
bookmarks = doc.get_bookmark_names()
```

#### Properties

- `com_document`: Get the underlying COM Document object for advanced operations
- `com_application`: Get the underlying COM Application object for advanced operations

## Complete Example

```python
from pathlib import Path
from paradoc.io.word.com_api import WordApplication

output_path = Path("report.docx")

with WordApplication(visible=False) as word_app:
    doc = word_app.create_document()
    
    # Title
    doc.add_heading("Technical Report", level=1)
    
    # Introduction
    doc.add_heading("Introduction", level=2)
    doc.add_paragraph("This report presents the findings of our study.")
    doc.add_paragraph()
    
    # Section with figures
    doc.add_heading("Results", level=2)
    doc.add_paragraph("The main results are shown below.")
    doc.add_paragraph()
    
    # Add figures
    fig1_bookmark = doc.add_figure_with_caption(
        caption_text="Experimental Setup",
        image_path="setup.png"
    )
    
    doc.add_paragraph()
    
    fig2_bookmark = doc.add_figure_with_caption(
        caption_text="Results Overview",
        image_path="results.png"
    )
    
    doc.add_paragraph()
    
    # Add table
    table_bookmark = doc.add_table_with_caption(
        caption_text="Measurement Data",
        rows=4,
        cols=3
    )
    
    doc.add_paragraph()
    
    # Discussion with cross-references
    doc.add_heading("Discussion", level=2)
    doc.add_cross_reference("figure_0", prefix_text="As shown in ")
    doc.add_paragraph(", the experimental setup was configured properly.")
    
    doc.add_paragraph()
    doc.add_cross_reference("table_0", prefix_text="The data in ")
    doc.add_paragraph(" confirms our hypothesis.")
    
    # New section
    doc.add_section_break("next_page")
    doc.add_heading("Conclusion", level=2)
    doc.add_paragraph("In conclusion, this study demonstrates...")
    
    # Update all fields and save
    doc.update_fields()
    doc.save(output_path)

print(f"Document created: {output_path}")
```

## Implementation Details

### SEQ Fields

The wrapper uses Word's built-in SEQ (Sequence) fields for automatic figure and table numbering:
- Figures: `SEQ Figure \* ARABIC`
- Tables: `SEQ Table \* ARABIC`

This ensures that numbering is automatically updated when figures or tables are added, removed, or reordered.

### Bookmarks

When `create_bookmark=True`, the wrapper automatically creates Word bookmarks with the pattern `_RefXXXXXXXXX` (timestamp-based). These bookmarks can be referenced using the symbolic names `figure_0`, `figure_1`, etc., or `table_0`, `table_1`, etc.

### Field Updates

Always call `doc.update_fields()` before saving to ensure all cross-references and SEQ fields display the correct values.

## Error Handling

The wrapper includes retry logic for common COM operations that may fail transiently, such as saving documents. It also provides proper cleanup through context managers to ensure Word is properly closed even if errors occur.

## Limitations

- Only available on Windows with Microsoft Word installed
- Requires the `pywin32` package
- Some Word features may behave differently depending on Word version and configuration
- Cross-reference insertion uses item indices, which works well for newly created documents but may require adjustment for complex existing documents

## See Also

- Original test case: `tests/figures/test_reverse_engineer_word_xref.py`
- Test suite: `tests/test_com_api_wrapper.py`
