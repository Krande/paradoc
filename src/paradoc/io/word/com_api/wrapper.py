"""Word COM API wrapper for simplified document creation.

This module provides high-level wrapper classes around win32com for Word automation.
"""

import platform
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Literal, Union

# Constants for Word COM API
WD_STORY = 6  # End of document
WD_FIELD_EMPTY = -1
WD_REF_TYPE_FIGURE = "Figure"
WD_REF_TYPE_TABLE = "Table"
WD_ONLY_LABEL_AND_NUMBER = 3
WD_FULL_CAPTION = 1
WD_MSO_SHAPE_RECTANGLE = 1

# Text wrapping constants for Word shapes
WD_WRAP_INLINE = 7  # wdWrapInline
WD_WRAP_SQUARE = 0  # wdWrapSquare
WD_WRAP_TIGHT = 1  # wdWrapTight
WD_WRAP_THROUGH = 2  # wdWrapThrough
WD_WRAP_TOP_BOTTOM = 3  # wdWrapTopAndBottom
WD_WRAP_BEHIND = 3  # wdWrapBehind (uses different enum)
WD_WRAP_FRONT = 4  # wdWrapInFrontOf (uses different enum)


class FigureLayout(str, Enum):
    """Layout options for figures in Word documents.

    Determines how text wraps around the figure.
    """

    INLINE = "inline"  # Inline with text (default)
    SQUARE = "square"  # Square wrapping around the figure
    TIGHT = "tight"  # Tight wrapping following figure outline
    THROUGH = "through"  # Text wraps through transparent areas
    TOP_BOTTOM = "top_bottom"  # Text above and below only
    BEHIND_TEXT = "behind_text"  # Figure behind text
    IN_FRONT_OF_TEXT = "in_front_of_text"  # Figure in front of text


@dataclass
class CaptionReference:
    """Reference to a figure or table caption for cross-referencing.

    This class encapsulates all information needed to create a cross-reference
    to a figure or table caption. It is returned by add_figure_with_caption and
    add_table_with_caption methods and can be passed directly to add_cross_reference.

    Attributes:
        bookmark_name: The Word bookmark name for the caption
        id: The sequential ID (0-based index) of the caption
        reference_type: The type of caption ("figure" or "table")
    """

    bookmark_name: str
    id: int
    reference_type: Literal["figure", "table"]


class WordApplication:
    """Wrapper for Word.Application COM object.

    Manages the Word application instance and provides methods for creating
    and opening documents.

    Example:
        with WordApplication(visible=False) as word_app:
            doc = word_app.create_document()
            doc.add_heading("My Document")
            doc.save("output.docx")
    """

    def __init__(self, visible: bool = False):
        """Initialize Word application.

        Args:
            visible: Whether to show the Word application window

        Raises:
            ImportError: If win32com is not available (non-Windows platform)
            RuntimeError: If Word application cannot be started
        """
        if platform.system() != "Windows":
            raise ImportError("Word COM automation is only available on Windows")

        try:
            import win32com.client as com_client

            self._com = com_client
        except ImportError:
            raise ImportError("pywin32 package is required for Word COM automation")

        self._app = None
        self._visible = visible
        self._documents = []

    def __enter__(self):
        """Context manager entry - start Word application."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - quit Word application."""
        self.quit()
        return False

    def start(self):
        """Start the Word application."""
        if self._app is None:
            # Use DispatchEx for late-binding
            self._app = self._com.DispatchEx("Word.Application")
            self._app.Visible = self._visible

    def quit(self):
        """Quit the Word application and close all documents."""
        if self._app is not None:
            # Close all tracked documents
            for doc in self._documents[:]:
                try:
                    doc.close(save_changes=False)
                except:
                    pass

            try:
                self._app.Quit()
            except:
                pass
            finally:
                self._app = None

    def create_document(self, template: Optional[Union[str, Path]] = None) -> "WordDocument":
        """Create a new Word document.

        Args:
            template: Optional path to a template .docx file to base the document on.
                     If provided, the document will use styles and formatting from the template.

        Returns:
            WordDocument wrapper around the new document
        """
        if self._app is None:
            self.start()

        if template is not None:
            template_path = str(Path(template).absolute())
            com_doc = self._app.Documents.Add(Template=template_path)
            # Move cursor to end of document so new content appears after template content
            self._app.Selection.EndKey(Unit=WD_STORY)
        else:
            com_doc = self._app.Documents.Add()
        doc = WordDocument(self._app, com_doc)
        self._documents.append(doc)
        return doc

    def open_document(self, path: Union[str, Path]) -> "WordDocument":
        """Open an existing Word document.

        Args:
            path: Path to the document file

        Returns:
            WordDocument wrapper around the opened document
        """
        if self._app is None:
            self.start()

        path = Path(path).absolute()
        com_doc = self._app.Documents.Open(str(path))
        doc = WordDocument(self._app, com_doc)
        self._documents.append(doc)
        return doc

    @property
    def visible(self) -> bool:
        """Get/set Word application visibility."""
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value
        if self._app is not None:
            self._app.Visible = value


class WordDocument:
    """Wrapper for a Word document COM object.

    Provides high-level methods for adding content and creating cross-references.
    """

    def __init__(self, app_com, doc_com):
        """Initialize document wrapper.

        Args:
            app_com: Word.Application COM object
            doc_com: Word.Document COM object
        """
        self._app = app_com
        self._doc = doc_com
        self._figure_count = 0
        self._table_count = 0
        self._bookmarks = {}

    def add_heading(self, text: str, level: int = 1):
        """Add a heading to the document.

        Args:
            text: The heading text
            level: The heading level (1-9, where 1 is "Heading 1")
        """
        if level < 1 or level > 9:
            raise ValueError("Heading level must be between 1 and 9")

        style = f"Heading {level}"
        self._app.Selection.Style = style
        self._app.Selection.TypeText(text)
        self._app.Selection.TypeParagraph()

    def add_paragraph(self, text: str = "", style: str = "Normal"):
        """Add a paragraph to the document.

        Args:
            text: The paragraph text (optional)
            style: The paragraph style (default: "Normal")
        """
        self._app.Selection.Style = style
        if text:
            self._app.Selection.TypeText(text)
        self._app.Selection.TypeParagraph()

    def add_text(self, text: str):
        """Add text at the current cursor position without creating a new paragraph.

        This is useful for adding text inline, such as continuing on the same line
        after inserting a cross-reference.

        Args:
            text: The text to insert
        """
        self._app.Selection.TypeText(text)

    def _apply_text_wrapping(self, shape, layout: FigureLayout):
        """Apply text wrapping to a shape based on layout type.

        Args:
            shape: Word Shape COM object
            layout: FigureLayout enum value
        """
        # Map layout enum to Word wrapping constants
        if layout == FigureLayout.SQUARE:
            shape.WrapFormat.Type = WD_WRAP_SQUARE
        elif layout == FigureLayout.TIGHT:
            shape.WrapFormat.Type = WD_WRAP_TIGHT
        elif layout == FigureLayout.THROUGH:
            shape.WrapFormat.Type = WD_WRAP_THROUGH
        elif layout == FigureLayout.TOP_BOTTOM:
            shape.WrapFormat.Type = WD_WRAP_TOP_BOTTOM
        elif layout == FigureLayout.BEHIND_TEXT:
            shape.WrapFormat.Type = WD_WRAP_SQUARE  # Use square as base
            shape.ZOrder(0)  # Send to back (behind text)
        elif layout == FigureLayout.IN_FRONT_OF_TEXT:
            shape.WrapFormat.Type = WD_WRAP_SQUARE  # Use square as base
            shape.ZOrder(1)  # Bring to front (in front of text)

    def add_page_break(self):
        """Insert a page break."""
        self._app.Selection.InsertBreak(7)  # wdPageBreak = 7

    def add_section_break(self, break_type: Literal["next_page", "continuous", "even_page", "odd_page"] = "next_page"):
        """Insert a section break.

        Args:
            break_type: Type of section break:
                - "next_page": Start on next page (default)
                - "continuous": Continue on same page
                - "even_page": Start on next even page
                - "odd_page": Start on next odd page
        """
        break_constants = {
            "next_page": 2,  # wdSectionBreakNextPage
            "continuous": 3,  # wdSectionBreakContinuous
            "even_page": 4,  # wdSectionBreakEvenPage
            "odd_page": 5,  # wdSectionBreakOddPage
        }

        if break_type not in break_constants:
            raise ValueError(f"Invalid break_type: {break_type}")

        self._app.Selection.InsertBreak(break_constants[break_type])

    def add_figure_with_caption(
        self,
        caption_text: str,
        image_path: Optional[Union[str, Path]] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        layout: Union[FigureLayout, str] = FigureLayout.INLINE,
        create_bookmark: bool = True,
        use_chapter_numbers: bool = True,
    ) -> Optional[CaptionReference]:
        """Add a figure with a caption.

        If image_path is provided, inserts the image. Otherwise, creates a placeholder shape.
        The caption uses a SEQ field for automatic numbering.

        Args:
            caption_text: The caption text (without "Figure X:" prefix)
            image_path: Optional path to image file to insert
            width: Optional width for image/shape in points
            height: Optional height for image/shape in points
            layout: Layout/text wrapping style for the figure (default: inline with text)
            create_bookmark: Whether to create a bookmark for cross-referencing
            use_chapter_numbers: Whether to use chapter-based numbering (e.g., 1.1, 1.2, 2.1).
                                Requires Heading 1 styles in the document. Default is False (simple numbering).

        Returns:
            CaptionReference object if create_bookmark=True, otherwise None
        """
        # Convert string to enum if needed
        if isinstance(layout, str):
            layout = FigureLayout(layout)

        # Insert figure (image or placeholder)
        if image_path is not None:
            image_path = Path(image_path).absolute()
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")

            # Insert image as inline shape first
            inline_shape = self._app.Selection.InlineShapes.AddPicture(
                FileName=str(image_path), LinkToFile=False, SaveWithDocument=True
            )

            # Resize if dimensions provided
            if width is not None:
                inline_shape.Width = width
            if height is not None:
                inline_shape.Height = height

            # Convert to floating shape if non-inline layout requested
            if layout != FigureLayout.INLINE:
                shape = inline_shape.ConvertToShape()
                self._apply_text_wrapping(shape, layout)
        else:
            # Create placeholder shape
            width = width or 100
            height = height or 100

            # Always create as floating shape first
            shape = self._doc.Shapes.AddShape(WD_MSO_SHAPE_RECTANGLE, 100, 100, width, height)

            if layout == FigureLayout.INLINE:
                # For inline layout, set wrapping to inline (wdWrapInline = 7)
                shape.WrapFormat.Type = WD_WRAP_INLINE
            else:
                # For other layouts, apply the specific text wrapping
                self._apply_text_wrapping(shape, layout)

        # Move to end and add caption
        self._app.Selection.EndKey(Unit=WD_STORY)
        self._app.Selection.TypeParagraph()
        self._app.Selection.Style = "Caption"

        # Create caption with SEQ field
        self._app.Selection.TypeText("Figure ")

        if use_chapter_numbers:
            # Use chapter-based numbering with hyphen separator (e.g., 1-1, 1-2, 2-1)
            # Format: { STYLEREF 1 \s }-{ SEQ Figure \* ARABIC \s 1 }
            # STYLEREF gets the heading 1 number, SEQ counts within that chapter
            # \s 1 switch makes SEQ track Heading 1 and reset when it changes

            # Add STYLEREF field for chapter number
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range, Type=WD_FIELD_EMPTY, Text="STYLEREF 1 \\s", PreserveFormatting=True
            )
            # Add hyphen separator
            self._app.Selection.TypeText("-")
            # Add SEQ field that resets per chapter and increments within chapter
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range,
                Type=WD_FIELD_EMPTY,
                Text="SEQ Figure \\* ARABIC \\s 1",
                PreserveFormatting=True,
            )
        else:
            # Simple sequential numbering (1, 2, 3, ...)
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range,
                Type=WD_FIELD_EMPTY,
                Text="SEQ Figure \\* ARABIC",
                PreserveFormatting=True,
            )

        self._app.Selection.TypeText(f": {caption_text}")

        # Create bookmark if requested
        caption_ref = None
        if create_bookmark:
            caption_range = self._app.Selection.Paragraphs(1).Range
            bookmark_name = f"_Ref{int(time.time() * 1000) % 1000000000}"
            self._doc.Bookmarks.Add(bookmark_name, caption_range)
            self._bookmarks[f"figure_{self._figure_count}"] = bookmark_name
            caption_ref = CaptionReference(bookmark_name=bookmark_name, id=self._figure_count, reference_type="figure")
            self._figure_count += 1

        self._app.Selection.TypeParagraph()
        return caption_ref

    def add_table_with_caption(
        self,
        caption_text: str,
        rows: int = 2,
        cols: int = 2,
        data: Optional[list[list]] = None,
        create_bookmark: bool = True,
        use_chapter_numbers: bool = True,
    ) -> Optional[CaptionReference]:
        """Add a table with a caption.

        The caption uses a SEQ field for automatic numbering.

        Args:
            caption_text: The caption text (without "Table X:" prefix)
            rows: Number of rows in the table
            cols: Number of columns in the table
            data: Optional data to populate the table. Should be a list of lists where
                  each inner list represents a row. If provided, the dimensions should
                  match the table size (rows x cols). Values will be converted to strings.
            create_bookmark: Whether to create a bookmark for cross-referencing
            use_chapter_numbers: Whether to use chapter-based numbering (e.g., 1.1, 1.2, 2.1).
                                Requires Heading 1 styles in the document. Default is False (simple numbering).

        Returns:
            CaptionReference object if create_bookmark=True, otherwise None
        """
        # Validate data dimensions if provided
        if data is not None:
            if len(data) != rows:
                raise ValueError(f"Data has {len(data)} rows but table has {rows} rows")
            for i, row in enumerate(data):
                if len(row) != cols:
                    raise ValueError(f"Data row {i} has {len(row)} columns but table has {cols} columns")

        # Insert table
        table_range = self._app.Selection.Range
        table = self._doc.Tables.Add(table_range, rows, cols)

        # Populate table with data if provided
        if data is not None:
            for row_idx, row_data in enumerate(data, start=1):  # Word uses 1-based indexing
                for col_idx, cell_value in enumerate(row_data, start=1):
                    table.Cell(row_idx, col_idx).Range.Text = str(cell_value)

        # Move past the table
        self._app.Selection.EndKey(Unit=WD_STORY)
        self._app.Selection.TypeParagraph()
        self._app.Selection.Style = "Caption"

        # Create caption with SEQ field
        self._app.Selection.TypeText("Table ")

        if use_chapter_numbers:
            # Use chapter-based numbering with hyphen separator (e.g., 1-1, 1-2, 2-1)
            # Format: { STYLEREF 1 \s }-{ SEQ Table \* ARABIC \s 1 }
            # STYLEREF gets the heading 1 number, SEQ counts within that chapter
            # \s 1 switch makes SEQ track Heading 1 and reset when it changes

            # Add STYLEREF field for chapter number
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range, Type=WD_FIELD_EMPTY, Text="STYLEREF 1 \\s", PreserveFormatting=True
            )
            # Add hyphen separator
            self._app.Selection.TypeText("-")
            # Add SEQ field that resets per chapter and increments within chapter
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range,
                Type=WD_FIELD_EMPTY,
                Text="SEQ Table \\* ARABIC \\s 1",
                PreserveFormatting=True,
            )
        else:
            # Simple sequential numbering (1, 2, 3, ...)
            self._app.Selection.Fields.Add(
                Range=self._app.Selection.Range,
                Type=WD_FIELD_EMPTY,
                Text="SEQ Table \\* ARABIC",
                PreserveFormatting=True,
            )

        self._app.Selection.TypeText(f": {caption_text}")

        # Create bookmark if requested
        caption_ref = None
        if create_bookmark:
            caption_range = self._app.Selection.Paragraphs(1).Range
            bookmark_name = f"_Ref{int(time.time() * 1000) % 1000000000}"
            self._doc.Bookmarks.Add(bookmark_name, caption_range)
            self._bookmarks[f"table_{self._table_count}"] = bookmark_name
            caption_ref = CaptionReference(bookmark_name=bookmark_name, id=self._table_count, reference_type="table")
            self._table_count += 1

        self._app.Selection.TypeParagraph()
        return caption_ref

    def add_cross_reference(
        self,
        bookmark_name: Union[CaptionReference, str, int],
        reference_type: Optional[Literal["figure", "table"]] = None,
        include_hyperlink: bool = True,
        prefix_text: str = "",
        include_caption_text: bool = False,
    ):
        """Add a cross-reference to a figure or table.

        Args:
            bookmark_name: Either a CaptionReference object (returned from add_figure_with_caption
                          or add_table_with_caption), a bookmark name string, or an integer index.
                          When passing a CaptionReference, reference_type is automatically extracted.
            reference_type: Type of reference ("figure" or "table"). Required only when bookmark_name
                           is a string or int. Ignored when bookmark_name is a CaptionReference.
            include_hyperlink: Whether to make the reference a clickable hyperlink
            prefix_text: Optional text to insert before the reference (e.g., "See ")
            include_caption_text: If True, inserts the full caption (label, number, and caption text).
                                  If False (default), inserts only label and number.
        """
        # Handle CaptionReference object
        if isinstance(bookmark_name, CaptionReference):
            actual_bookmark_name = bookmark_name.id  # Use the id for item index
            actual_reference_type = bookmark_name.reference_type
        else:
            # Legacy behavior: bookmark_name is str or int
            actual_bookmark_name = bookmark_name
            if reference_type is None:
                raise ValueError("reference_type must be provided when bookmark_name is not a CaptionReference")
            actual_reference_type = reference_type

        if prefix_text:
            self._app.Selection.TypeText(prefix_text)

        # Map reference type to Word constant
        ref_type_map = {"figure": WD_REF_TYPE_FIGURE, "table": WD_REF_TYPE_TABLE}

        if actual_reference_type not in ref_type_map:
            raise ValueError(f"Invalid reference_type: {actual_reference_type}")

        # If actual_bookmark_name is an integer or a key like "figure_0", resolve it
        if isinstance(actual_bookmark_name, int):
            item_index = actual_bookmark_name + 1  # Word uses 1-based indexing
        elif actual_bookmark_name in self._bookmarks:
            # This is a symbolic reference - need to find the item index
            # For now, just use the numeric suffix + 1
            item_index = int(actual_bookmark_name.split("_")[-1]) + 1
        else:
            # Assume it's already a bookmark name - find its position
            # For simplicity, we'll try to insert by item number based on count
            item_index = 1

        try:
            self._app.Selection.InsertCrossReference(
                ReferenceType=ref_type_map[actual_reference_type],
                ReferenceKind=WD_FULL_CAPTION if include_caption_text else WD_ONLY_LABEL_AND_NUMBER,
                ReferenceItem=item_index,
                InsertAsHyperlink=include_hyperlink,
                IncludePosition=False,
            )
            # Collapse selection to end to ensure cursor stays on the same line
            # This prevents Word from inserting a paragraph break
            self._app.Selection.Collapse(Direction=0)  # wdCollapseEnd = 0
        except Exception as e:
            raise RuntimeError(f"Failed to insert cross-reference: {e}")

    def update_fields(self):
        """Update all fields in the document."""
        try:
            self._doc.Fields.Update()
        except Exception as e:
            # Field update failures are often non-critical
            print(f"Warning: Field update failed: {e}")

    def save(self, path: Union[str, Path]):
        """Save the document.

        Args:
            path: Path where to save the document
        """
        path = Path(path).absolute()

        # Wait a moment for Word to finish processing
        time.sleep(0.5)

        try:
            self._doc.SaveAs(str(path))
        except Exception as e:
            # Retry once after a short delay
            time.sleep(1)
            try:
                self._doc.SaveAs(str(path))
            except Exception as retry_e:
                raise RuntimeError(f"Failed to save document: {retry_e}") from e

    def close(self, save_changes: bool = False):
        """Close the document.

        Args:
            save_changes: Whether to save changes before closing
        """
        try:
            self._doc.Close(SaveChanges=save_changes)
        except Exception as e:
            print(f"Warning: Failed to close document: {e}")

    def get_bookmark_names(self) -> list[str]:
        """Get all bookmark names in the document.

        Returns:
            List of bookmark names
        """
        try:
            return [bm.Name for bm in self._doc.Bookmarks]
        except:
            return []

    @property
    def com_document(self):
        """Get the underlying COM Document object for advanced operations."""
        return self._doc

    @property
    def com_application(self):
        """Get the underlying COM Application object for advanced operations."""
        return self._app
