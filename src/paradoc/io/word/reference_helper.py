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
            document_order=len(self._all_items),
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
            document_order=len(self._all_items),
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
            document_order=len(self._all_items),
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
                number_match = re.search(r"(\d+[-.]\d+)", text)
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

        # Build mapping dictionaries and patterns for all reference types
        ref_configs = []

        # Configure figures
        figure_bookmarks = self.get_all_figure_bookmarks_in_order()
        if figure_bookmarks:
            print(f"[ReferenceHelper] Preparing {len(figure_bookmarks)} figure references")
            fig_items = [item for item in self._all_items if item.ref_type == ReferenceType.FIGURE]
            fig_display_to_idx = {}
            fig_sequential_to_idx = {}
            for idx, item in enumerate(fig_items):
                fig_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    fig_display_to_idx[item.display_number] = idx
                    print(f"[ReferenceHelper]   Figure #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    print(f"[ReferenceHelper]   Figure #{idx}: (no display number) -> {item.word_bookmark}")

            ref_configs.append(
                {
                    "label": "Figure",
                    "pattern": re.compile(r"\b(?:Figure|fig\.)[\s\xa0]*([\d.\-]+)", re.IGNORECASE),
                    "bookmarks": figure_bookmarks,
                    "display_to_idx": fig_display_to_idx,
                    "sequential_to_idx": fig_sequential_to_idx,
                    "num_group": 1,
                }
            )

        # Configure tables
        table_bookmarks = self.get_all_table_bookmarks_in_order()
        if table_bookmarks:
            print(f"[ReferenceHelper] Preparing {len(table_bookmarks)} table references")
            tbl_items = [item for item in self._all_items if item.ref_type == ReferenceType.TABLE]
            tbl_display_to_idx = {}
            tbl_sequential_to_idx = {}
            for idx, item in enumerate(tbl_items):
                tbl_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    tbl_display_to_idx[item.display_number] = idx
                    print(f"[ReferenceHelper]   Table #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    print(f"[ReferenceHelper]   Table #{idx}: (no display number) -> {item.word_bookmark}")

            ref_configs.append(
                {
                    "label": "Table",
                    "pattern": re.compile(r"\b(?:Table|tbl\.)[\s\xa0]*([\d.\-]+)", re.IGNORECASE),
                    "bookmarks": table_bookmarks,
                    "display_to_idx": tbl_display_to_idx,
                    "sequential_to_idx": tbl_sequential_to_idx,
                    "num_group": 1,
                }
            )

        # Configure equations
        equation_bookmarks = self.get_all_equation_bookmarks_in_order()
        if equation_bookmarks:
            print(f"[ReferenceHelper] Preparing {len(equation_bookmarks)} equation references")
            eq_items = [item for item in self._all_items if item.ref_type == ReferenceType.EQUATION]
            eq_display_to_idx = {}
            eq_sequential_to_idx = {}
            for idx, item in enumerate(eq_items):
                eq_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    eq_display_to_idx[item.display_number] = idx
                    print(f"[ReferenceHelper]   Eq #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    print(f"[ReferenceHelper]   Eq #{idx}: (no display number) -> {item.word_bookmark}")

            ref_configs.append(
                {
                    "label": "Eq",
                    "pattern": re.compile(r"\b((?:Eq(?:uation)?|eq\.)\s+([\d\-]+))\b", re.IGNORECASE),
                    "bookmarks": equation_bookmarks,
                    "display_to_idx": eq_display_to_idx,
                    "sequential_to_idx": eq_sequential_to_idx,
                    "num_group": 2,
                }
            )

        # Skip caption paragraphs
        caption_styles = {"Image Caption", "Table Caption", "Captioned Figure"}

        # Process all paragraphs ONCE, handling all reference types
        processed_count = 0
        for block in iter_block_items(document):
            if not isinstance(block, Paragraph):
                continue

            # Skip caption paragraphs
            if block.style.name in caption_styles:
                continue

            # Check if paragraph contains any references
            paragraph_text = block.text
            has_refs = any(re.search(cfg["pattern"], paragraph_text) for cfg in ref_configs)
            if not has_refs:
                continue

            # Process this paragraph for ALL reference types at once
            print(f"[ReferenceHelper] Processing paragraph: {paragraph_text[:80]}")
            self._process_paragraph_all_refs(block, ref_configs)
            processed_count += 1

        print(f"[ReferenceHelper] Conversion complete: {processed_count} paragraphs processed")

    def _process_paragraph_all_refs(self, paragraph: Paragraph, ref_configs: List[Dict]):
        """Process a paragraph to replace ALL reference types with REF fields in one pass.

        This avoids the problem of clearing the paragraph multiple times, which would remove
        REF fields added in previous passes.

        Args:
            paragraph: The paragraph to process
            ref_configs: List of reference configurations, each containing:
                - label: The label for REF fields (e.g., "Figure", "Table")
                - pattern: Regex pattern to match references
                - bookmarks: List of bookmark names in order
                - display_to_idx: Mapping of display numbers to indices
                - sequential_to_idx: Mapping of sequential numbers to indices
                - num_group: The regex group containing the number
        """
        original_text = paragraph.text

        # Find ALL matches from ALL patterns, with their positions
        all_matches = []
        for config in ref_configs:
            for match in config["pattern"].finditer(original_text):
                all_matches.append({"start": match.start(), "end": match.end(), "match": match, "config": config})

        if not all_matches:
            return

        # Sort matches by position
        all_matches.sort(key=lambda x: x["start"])

        # Check for overlapping matches and keep only the first one for each position
        non_overlapping = []
        last_end = 0
        for m in all_matches:
            if m["start"] >= last_end:
                non_overlapping.append(m)
                last_end = m["end"]

        print(f"[ReferenceHelper]   Found {len(non_overlapping)} reference(s)")

        # Store paragraph element before clearing
        p_element = paragraph._p

        # Clear all runs and hyperlinks
        for run in list(paragraph.runs):
            p_element.remove(run._element)
        for child in list(p_element):
            if child.tag == qn("w:hyperlink"):
                p_element.remove(child)

        # Rebuild the paragraph with text and REF fields
        last_pos = 0
        ref_fields_added = 0

        for match_info in non_overlapping:
            match = match_info["match"]
            config = match_info["config"]
            label = config["label"]
            bookmarks = config["bookmarks"]
            display_to_idx = config["display_to_idx"]
            sequential_to_idx = config["sequential_to_idx"]
            num_group = config["num_group"]

            # Extract the number from the matched text
            if num_group == 2:
                # For equations: group 1 is full match, group 2 is number
                num_str = match.group(2)
            else:
                # For figures/tables: group 1 is number
                num_str = match.group(1).split()[-1] if " " in match.group(1) else match.group(1)

            # Strip trailing periods that may have been captured by the regex
            # (e.g., "1." becomes "1", "1-1." becomes "1-1")
            num_str = num_str.rstrip(".")

            # Map the reference number to the bookmark index
            bookmark_idx = None
            if num_str in display_to_idx:
                bookmark_idx = display_to_idx[num_str]
                print(f"[ReferenceHelper]     {label} '{num_str}' matched display number -> index {bookmark_idx}")
            elif num_str in sequential_to_idx:
                bookmark_idx = sequential_to_idx[num_str]
                print(f"[ReferenceHelper]     {label} '{num_str}' matched sequential number -> index {bookmark_idx}")
            else:
                print(f"[ReferenceHelper]     WARNING: No mapping for {label} '{num_str}', skipping")
                continue

            # Get the bookmark name
            if 0 <= bookmark_idx < len(bookmarks):
                bookmark_name = bookmarks[bookmark_idx]
            else:
                print(f"[ReferenceHelper]     WARNING: Index {bookmark_idx} out of range (max {len(bookmarks) - 1})")
                continue

            # Add text before the reference
            if match.start() > last_pos:
                before_text = original_text[last_pos : match.start()]
                create_text_run(p_element, before_text)

            # Add REF field
            create_ref_field_runs(p_element, bookmark_name, label=label)
            ref_fields_added += 1
            print(f"[ReferenceHelper]     Added {label} REF field: '{num_str}' -> bookmark '{bookmark_name}'")

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
            "total": len(self._all_items),
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
            print(
                f"    [{item.document_order}] {item.ref_type.value} '{item.semantic_id}' -> {item.word_bookmark} (display: {item.display_number})"
            )
