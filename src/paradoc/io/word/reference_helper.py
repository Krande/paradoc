"""Reference management system for Word cross-references.

This module provides a centralized ReferenceHelper class that manages all cross-references
(figures, tables, equations) throughout the Word document compilation process.

Key Features:
- Maintains a registry of all cross-referenceable items
- Generates Word-compatible bookmark names
- Tracks both semantic names (e.g., "fig:test_figure") and Word-style names (e.g., "_Ref306075071")
- Provides methods to create REF fields that correctly point to bookmarks
- Ensures proper linking between references and their targets
"""

import random
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .fields import create_ref_field_runs, create_text_run
from .utils import iter_block_items


class ReferenceType(Enum):
    """Types of cross-referenceable items."""
    FIGURE = "Figure"
    TABLE = "Table"
    EQUATION = "Eq"


@dataclass
class ReferenceItem:
    """Represents a single cross-referenceable item (figure, table, or equation).

    Attributes:
        ref_type: The type of reference (FIGURE, TABLE, or EQUATION)
        semantic_id: The semantic identifier (e.g., "test_figure" from "fig:test_figure")
        word_bookmark: The Word-style bookmark name (e.g., "_Ref306075071")
        display_number: The display number (e.g., "1-1", "2-3")
        caption_paragraph: The actual Word paragraph containing the caption
        document_order: Sequential order in the document (0, 1, 2, ...)
    """
    ref_type: ReferenceType
    semantic_id: str
    word_bookmark: str
    display_number: Optional[str] = None
    caption_paragraph: Optional[Paragraph] = None
    document_order: int = 0


class ReferenceHelper:
    """Central manager for all cross-references in a Word document.

    This class maintains a registry of all figures, tables, and equations,
    generates consistent bookmark names, and provides utilities for converting
    text references to REF fields.

    Usage:
        helper = ReferenceHelper()

        # Register a figure when formatting it
        bookmark = helper.register_figure("test_figure", caption_para)

        # Later, convert all text references to REF fields
        helper.convert_all_references(document)
    """

    def __init__(self):
        """Initialize the reference helper with empty registries."""
        self._figures: Dict[str, ReferenceItem] = {}
        self._tables: Dict[str, ReferenceItem] = {}
        self._equations: Dict[str, ReferenceItem] = {}
        self._all_items: List[ReferenceItem] = []  # All items in document order
        self._bookmark_counter = 0

    def _generate_word_bookmark(self) -> str:
        """Generate a unique Word-style bookmark name.

        Returns:
            A bookmark name like "_Ref306075071"
        """
        # Generate random 9-digit number for Word-style bookmark
        random_id = random.randint(100000000, 999999999)
        return f"_Ref{random_id}"

    def register_figure(self, semantic_id: str, caption_para: Optional[Paragraph] = None) -> str:
        """Register a figure and get its Word bookmark name.

        Args:
            semantic_id: The semantic identifier (e.g., "test_figure")
            caption_para: Optional caption paragraph for this figure

        Returns:
            The Word-style bookmark name to use
        """
        if semantic_id in self._figures:
            # Already registered, return existing bookmark
            return self._figures[semantic_id].word_bookmark

        bookmark = self._generate_word_bookmark()
        item = ReferenceItem(
            ref_type=ReferenceType.FIGURE,
            semantic_id=semantic_id,
            word_bookmark=bookmark,
            caption_paragraph=caption_para,
            document_order=len(self._all_items)
        )
        self._figures[semantic_id] = item
        self._all_items.append(item)
        return bookmark

    def register_table(self, semantic_id: str, caption_para: Optional[Paragraph] = None) -> str:
        """Register a table and get its Word bookmark name.

        Args:
            semantic_id: The semantic identifier (e.g., "results_table")
            caption_para: Optional caption paragraph for this table

        Returns:
            The Word-style bookmark name to use
        """
        if semantic_id in self._tables:
            # Already registered, return existing bookmark
            return self._tables[semantic_id].word_bookmark

        bookmark = self._generate_word_bookmark()
        item = ReferenceItem(
            ref_type=ReferenceType.TABLE,
            semantic_id=semantic_id,
            word_bookmark=bookmark,
            caption_paragraph=caption_para,
            document_order=len(self._all_items)
        )
        self._tables[semantic_id] = item
        self._all_items.append(item)
        return bookmark

    def register_equation(self, semantic_id: str, caption_para: Optional[Paragraph] = None) -> str:
        """Register an equation and get its Word bookmark name.

        Args:
            semantic_id: The semantic identifier (e.g., "maxwell_equation")
            caption_para: Optional caption paragraph for this equation

        Returns:
            The Word-style bookmark name to use
        """
        if semantic_id in self._equations:
            # Already registered, return existing bookmark
            return self._equations[semantic_id].word_bookmark

        bookmark = self._generate_word_bookmark()
        item = ReferenceItem(
            ref_type=ReferenceType.EQUATION,
            semantic_id=semantic_id,
            word_bookmark=bookmark,
            caption_paragraph=caption_para,
            document_order=len(self._all_items)
        )
        self._equations[semantic_id] = item
        self._all_items.append(item)
        return bookmark

    def get_figure_bookmark(self, semantic_id: str) -> Optional[str]:
        """Get the Word bookmark for a registered figure.

        Args:
            semantic_id: The semantic identifier

        Returns:
            The Word bookmark name, or None if not found
        """
        item = self._figures.get(semantic_id)
        return item.word_bookmark if item else None

    def get_table_bookmark(self, semantic_id: str) -> Optional[str]:
        """Get the Word bookmark for a registered table.

        Args:
            semantic_id: The semantic identifier

        Returns:
            The Word bookmark name, or None if not found
        """
        item = self._tables.get(semantic_id)
        return item.word_bookmark if item else None

    def get_equation_bookmark(self, semantic_id: str) -> Optional[str]:
        """Get the Word bookmark for a registered equation.

        Args:
            semantic_id: The semantic identifier

        Returns:
            The Word bookmark name, or None if not found
        """
        item = self._equations.get(semantic_id)
        return item.word_bookmark if item else None

    def get_all_figure_bookmarks_in_order(self) -> List[str]:
        """Get all figure bookmarks in document order.

        Returns:
            List of Word bookmark names for figures
        """
        figure_items = [item for item in self._all_items if item.ref_type == ReferenceType.FIGURE]
        return [item.word_bookmark for item in figure_items]

    def get_all_table_bookmarks_in_order(self) -> List[str]:
        """Get all table bookmarks in document order.

        Returns:
            List of Word bookmark names for tables
        """
        table_items = [item for item in self._all_items if item.ref_type == ReferenceType.TABLE]
        return [item.word_bookmark for item in table_items]

    def get_all_equation_bookmarks_in_order(self) -> List[str]:
        """Get all equation bookmarks in document order.

        Returns:
            List of Word bookmark names for equations
        """
        equation_items = [item for item in self._all_items if item.ref_type == ReferenceType.EQUATION]
        return [item.word_bookmark for item in equation_items]

    def update_display_numbers(self):
        """Update display numbers by scanning caption paragraphs.

        This should be called after all captions have been formatted and before
        converting references to REF fields.
        """
        for item in self._all_items:
            if item.caption_paragraph:
                # Extract the number from the caption text
                # Caption format: "Figure 2-1: Caption text" or "Table 1-1: Caption text"
                text = item.caption_paragraph.text
                number_match = re.search(r'(\d+[-.]\d+)', text)
                if number_match:
                    item.display_number = number_match.group(1)

    def convert_all_references(self, document):
        """Convert all text references to REF fields in the document.

        This method scans the entire document for text references (e.g., "Figure 1-1",
        "Table 2-3") and replaces them with proper Word REF fields that point to the
        registered bookmarks.

        Args:
            document: The Word document to process
        """
        print("[ReferenceHelper] Converting all references to REF fields")

        # Convert figures
        figure_bookmarks = self.get_all_figure_bookmarks_in_order()
        if figure_bookmarks:
            print(f"[ReferenceHelper] Converting {len(figure_bookmarks)} figure references")
            self._convert_references(
                document,
                figure_bookmarks,
                re.compile(r'\b(?:Figure|fig\.)[\s\xa0]*([\d.\-]+)', re.IGNORECASE),
                "Figure"
            )

        # Convert tables
        table_bookmarks = self.get_all_table_bookmarks_in_order()
        if table_bookmarks:
            print(f"[ReferenceHelper] Converting {len(table_bookmarks)} table references")
            self._convert_references(
                document,
                table_bookmarks,
                re.compile(r'\b(?:Table|tbl\.)[\s\xa0]*([\d.\-]+)', re.IGNORECASE),
                "Table"
            )

        # Convert equations
        equation_bookmarks = self.get_all_equation_bookmarks_in_order()
        if equation_bookmarks:
            print(f"[ReferenceHelper] Converting {len(equation_bookmarks)} equation references")
            self._convert_references(
                document,
                equation_bookmarks,
                re.compile(r'\b((?:Eq(?:uation)?|eq\.)\s+([\d\-]+))\b', re.IGNORECASE),
                "Eq",
                num_group=2
            )

    def _convert_references(self, document, bookmarks_in_order: List[str],
                          pattern: re.Pattern, label: str, num_group: int = 1):
        """Generic function to convert text references to REF fields.

        This is an improved version that uses the reference helper's knowledge
        of all registered items.

        Args:
            document: The Word document
            bookmarks_in_order: List of bookmark names in document order
            pattern: Regex pattern to match references
            label: The label to use in REF fields (e.g., "Figure", "Table", "Eq")
            num_group: The regex group number containing the number (default 1)
        """
        # Build a mapping of display numbers to bookmark indices
        reference_to_index = {}

        # Get all items of this type in document order
        if label == "Figure":
            items = [item for item in self._all_items if item.ref_type == ReferenceType.FIGURE]
        elif label == "Table":
            items = [item for item in self._all_items if item.ref_type == ReferenceType.TABLE]
        elif label == "Eq":
            items = [item for item in self._all_items if item.ref_type == ReferenceType.EQUATION]
        else:
            items = []

        # Map display numbers to indices
        for idx, item in enumerate(items):
            if item.display_number:
                reference_to_index[item.display_number] = idx
                print(f"[ReferenceHelper]   {label} #{idx}: {item.display_number} -> {item.word_bookmark}")

        # Skip caption paragraphs - we don't want to convert numbers in captions themselves
        caption_styles = {"Image Caption", "Table Caption", "Captioned Figure"}

        # Track occurrences for sequential matching
        reference_occurrence_count = {}

        # Process all paragraphs
        processed_count = 0
        for block in iter_block_items(document):
            if not isinstance(block, Paragraph):
                continue

            # Skip caption paragraphs
            if block.style.name in caption_styles:
                continue

            # Check if paragraph contains references
            if not re.search(pattern, block.text):
                continue

            # Process the paragraph
            print(f"[ReferenceHelper] Processing {label} references in: {block.text[:80]}")
            self._process_paragraph_references(
                block, pattern, bookmarks_in_order, label, num_group,
                reference_to_index, reference_occurrence_count
            )
            processed_count += 1

        print(f"[ReferenceHelper] {label} conversion complete: {processed_count} paragraphs processed")

    def _process_paragraph_references(self, paragraph: Paragraph, pattern: re.Pattern,
                                     bookmarks: List[str], label: str, num_group: int,
                                     reference_to_index: Dict[str, int],
                                     reference_occurrence_count: Dict[str, int]):
        """Process a single paragraph to replace text references with REF fields.

        Args:
            paragraph: The paragraph to process
            pattern: Regex pattern to match references
            bookmarks: List of bookmark names in order
            label: The label for REF fields
            num_group: The regex group containing the number
            reference_to_index: Mapping of reference numbers to sequential indices
            reference_occurrence_count: Track reference occurrences for sequential matching
        """
        original_text = paragraph.text
        matches = list(pattern.finditer(original_text))
        if not matches:
            return

        print(f"[ReferenceHelper]   Found {len(matches)} {label} reference(s)")

        # Store paragraph element before clearing
        p_element = paragraph._p

        # Clear all runs and hyperlinks
        for run in list(paragraph.runs):
            p_element.remove(run._element)
        for child in list(p_element):
            if child.tag == qn('w:hyperlink'):
                p_element.remove(child)

        # Rebuild the paragraph with text and REF fields
        last_pos = 0
        ref_fields_added = 0

        for match in matches:
            # Extract the number from the matched text
            if num_group == 2:
                # For equations: group 1 is full match, group 2 is number
                num_str = match.group(2)
            else:
                # For figures/tables: group 1 is number
                num_str = match.group(1).split()[-1] if ' ' in match.group(1) else match.group(1)

            # Map the reference number to the bookmark
            if num_str in reference_to_index:
                # Use the pre-built mapping
                bookmark_idx = reference_to_index[num_str]
            else:
                # Sequential fallback: use occurrence count
                if num_str not in reference_occurrence_count:
                    reference_occurrence_count[num_str] = 0
                bookmark_idx = reference_occurrence_count[num_str]
                reference_occurrence_count[num_str] += 1
                print(f"[ReferenceHelper]     No mapping for '{num_str}', using sequential index {bookmark_idx}")

            # Get the bookmark name
            if 0 <= bookmark_idx < len(bookmarks):
                bookmark_name = bookmarks[bookmark_idx]
            else:
                # Out of range, use last bookmark or skip
                print(f"[ReferenceHelper]     WARNING: Index {bookmark_idx} out of range (max {len(bookmarks)-1})")
                bookmark_name = bookmarks[-1] if bookmarks else None

            if bookmark_name is None:
                # No bookmark available, just add remaining text
                if last_pos < len(original_text):
                    create_text_run(p_element, original_text[last_pos:])
                break

            # Add text before the reference
            if match.start() > last_pos:
                before_text = original_text[last_pos:match.start()]
                create_text_run(p_element, before_text)

            # Add REF field
            create_ref_field_runs(p_element, bookmark_name, label=label)
            ref_fields_added += 1
            print(f"[ReferenceHelper]     Added REF field: '{num_str}' -> bookmark '{bookmark_name}'")

            last_pos = match.end()

        # Add remaining text after the last reference
        if last_pos < len(original_text):
            after_text = original_text[last_pos:]
            create_text_run(p_element, after_text)

        print(f"[ReferenceHelper]   Completed: {ref_fields_added} REF field(s) added")

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about registered references.

        Returns:
            Dictionary with counts of each reference type
        """
        return {
            "figures": len(self._figures),
            "tables": len(self._tables),
            "equations": len(self._equations),
            "total": len(self._all_items)
        }

    def print_registry(self):
        """Print the complete registry for debugging."""
        print("\n[ReferenceHelper] Complete Registry:")
        print(f"  Total items: {len(self._all_items)}")
        print(f"  Figures: {len(self._figures)}")
        print(f"  Tables: {len(self._tables)}")
        print(f"  Equations: {len(self._equations)}")
        print("\n  Items in document order:")
        for item in self._all_items:
            print(f"    [{item.document_order}] {item.ref_type.value} '{item.semantic_id}' -> {item.word_bookmark} (display: {item.display_number})")

