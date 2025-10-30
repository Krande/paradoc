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
from typing import Dict, List, Optional, Any

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from paradoc.config import logger

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


@dataclass
class HyperlinkReference:
    """Represents a hyperlink-based cross-reference that needs to be converted.

    This dataclass holds all necessary information to replace a hyperlink with
    a proper native Word cross-reference using REF and SEQ fields.

    Attributes:
        paragraph: The Word paragraph containing the hyperlink
        hyperlink_element: The XML element of the hyperlink
        anchor: The hyperlink anchor (e.g., "fig:test_figure")
        hyperlink_text: The text inside the hyperlink (e.g., "1")
        ref_type: The type of reference (FIGURE, TABLE, or EQUATION)
        semantic_id: The semantic identifier (e.g., "test_figure")
        word_bookmark: The Word-style bookmark name to reference (e.g., "_Ref306075071")
        label: The label for the REF field (e.g., "Figure", "Table", "Eq")
        prefix_text: The text before the hyperlink that should be removed (e.g., "fig.")
        prefix_run_element: The XML run element containing the prefix text (if any)
        element_index: Index of the hyperlink in the paragraph's children
    """

    paragraph: Paragraph
    hyperlink_element: Any  # XML element
    anchor: str
    hyperlink_text: str
    ref_type: ReferenceType
    semantic_id: str
    word_bookmark: str
    label: str
    prefix_text: Optional[str] = None
    prefix_run_element: Optional[Any] = None
    element_index: int = 0

    def __repr__(self) -> str:
        """Succinct, descriptive representation used for debugging/logging.

        Format example:
            HyperLink(refType=Table, refNum=1, anchor="tbl:'current_metrics'", pg="...two words before... Table 1 ...two words after...")

        Notes:
        - "pg" shows 2 words before and 2 words after the cross-reference location in the paragraph.
        - The cross-reference in the middle is normalized to "{label} {refNum}" regardless of how it is abbreviated in the paragraph.
        """
        try:
            # Normalize number
            ref_num = (self.hyperlink_text or "").strip().rstrip('.')
            label = self.ref_type.value if getattr(self, 'ref_type', None) else (self.label or "")

            # Attempt to extract two words before and after around our hyperlink element
            before_words: List[str] = []
            after_words: List[str] = []

            p_element = getattr(self.paragraph, '_p', None)
            target_elem = self.hyperlink_element

            def _text_from_element(elem: Any) -> str:
                # Gather all w:t text under element
                parts: List[str] = []
                for t in elem.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                    if t.text:
                        parts.append(t.text)
                    else:
                        parts.append("")
                return "".join(parts)

            def _tokenize_words(s: str) -> List[str]:
                # Keep only word-like tokens; ignore punctuation for context windows
                return [tok for tok in re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", s)]

            if p_element is not None and target_elem is not None:
                children = list(p_element)

                # Resolve index of our hyperlink in current paragraph children
                idx = None
                # Prefer stored element_index if it still matches the same element
                if 0 <= self.element_index < len(children) and children[self.element_index] is target_elem:
                    idx = self.element_index
                else:
                    # Fallback: locate by identity
                    for i, ch in enumerate(children):
                        if ch is target_elem:
                            idx = i
                            break

                if idx is not None:
                    # Build text before and after by concatenating siblings' text
                    before_text = "".join(_text_from_element(e) for e in children[:idx])
                    after_text = "".join(_text_from_element(e) for e in children[idx+1:])

                    # Remove known prefix abbreviation from the boundary of before_text
                    if self.prefix_text:
                        before_text = re.sub(re.escape(self.prefix_text) + r"\s*$", " ", before_text)

                    before_tokens = _tokenize_words(before_text)
                    after_tokens = _tokenize_words(after_text)

                    before_words = before_tokens[-2:] if len(before_tokens) >= 2 else before_tokens
                    after_words = after_tokens[:2] if len(after_tokens) >= 2 else after_tokens

            # Compose page context string
            parts = []
            if before_words:
                parts.append(" ".join(before_words))
            # The cross-reference itself, normalized to "Label N"
            center = f"{label} {ref_num}".strip()
            if center:
                parts.append(center)
            if after_words:
                parts.append(" ".join(after_words))

            pg = " ".join(p for p in parts if p)
            # Collapse multiple spaces
            pg = re.sub(r"\s+", " ", pg).strip()

            # Anchor formatted as in example: anchor="tbl:'semantic'"
            anchor_repr = self.anchor
            # Ensure quotes around semantic id part if present
            if ':' in anchor_repr:
                kind, sem = anchor_repr.split(':', 1)
                anchor_repr = f"{kind}:'{sem}'"

            return f"HyperLink(refType={label}, refNum={ref_num}, anchor=\"{anchor_repr}\", pg=\"{pg}\")"
        except Exception:
            # Fallback simple representation
            return f"HyperLink(refType={getattr(self.ref_type, 'value', self.label)}, refNum={self.hyperlink_text}, anchor=\"{self.anchor}\")"


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

    def extract_hyperlink_references(self, document) -> List[HyperlinkReference]:
        """Extract all hyperlink-based cross-references from the document.

        This method scans the document for hyperlinks created by pandoc-crossref
        (with linkReferences: true) and returns structured information about each
        reference that needs to be converted to a native Word REF field.

        This method is completely independent and does not rely on pre-registered items.
        It scans the entire document to find both hyperlinks and their target captions.

        Args:
            document: The Word document to scan

        Returns:
            List of HyperlinkReference objects containing all information needed
            for conversion to REF fields
        """
        logger.info("[ReferenceHelper] Extracting hyperlink-based cross-references")

        # First pass: Find all caption bookmarks in the document
        # These are the targets that hyperlinks will point to
        anchor_to_bookmark = {}  # Maps anchor (e.g., "fig:test_figure") to Word bookmark name
        anchor_to_info = {}      # Maps anchor to metadata (type, label, etc.)

        logger.debug("[ReferenceHelper] First pass: scanning for caption bookmarks...")

        for block in iter_block_items(document):
            if not isinstance(block, Paragraph):
                continue

            p_element = block._p

            # Look for bookmarkStart elements in captions
            bookmark_starts = p_element.findall('.//w:bookmarkStart', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

            for bm_start in bookmark_starts:
                bm_name = bm_start.get(qn('w:name'))
                if not bm_name or not bm_name.startswith('_Ref'):
                    continue

                # Check if this paragraph has a hyperlink with an anchor (pandoc-crossref creates these)
                hyperlinks_in_para = p_element.findall('.//w:hyperlink', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

                for hl in hyperlinks_in_para:
                    anchor = hl.get(qn('w:anchor'))
                    if not anchor:
                        continue

                    # Check if this looks like a pandoc-crossref anchor
                    if anchor.startswith('fig:'):
                        ref_type = ReferenceType.FIGURE
                        semantic_id = anchor[4:]
                        label = "Figure"
                    elif anchor.startswith('tbl:'):
                        ref_type = ReferenceType.TABLE
                        semantic_id = anchor[4:]
                        label = "Table"
                    elif anchor.startswith('eq:'):
                        ref_type = ReferenceType.EQUATION
                        semantic_id = anchor[3:]
                        label = "Eq"
                    else:
                        continue

                    # Store the mapping
                    anchor_to_bookmark[anchor] = bm_name
                    anchor_to_info[anchor] = {
                        'ref_type': ref_type,
                        'semantic_id': semantic_id,
                        'label': label,
                        'word_bookmark': bm_name
                    }

                    logger.debug(f"[ReferenceHelper]   Found caption bookmark: {anchor} -> {bm_name}")
                    break  # Only one anchor per caption paragraph

        logger.info(f"[ReferenceHelper] Found {len(anchor_to_bookmark)} caption bookmarks")

        # Second pass: Find all hyperlink references in the document
        # Skip caption paragraphs
        caption_styles = {"Image Caption", "Table Caption", "Captioned Figure"}

        hyperlink_refs = []

        logger.debug("[ReferenceHelper] Second pass: scanning for hyperlink references...")

        for block in iter_block_items(document):
            if not isinstance(block, Paragraph):
                continue

            # Skip caption paragraphs
            if block.style.name in caption_styles:
                continue

            p_element = block._p

            # Find ALL hyperlinks in the paragraph using xpath (not just direct children)
            hyperlinks = p_element.findall('.//w:hyperlink', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

            if not hyperlinks:
                continue

            # Convert to list for proper indexing (to find position in parent)
            children = list(p_element)

            # Scan all hyperlink elements found
            for hyperlink_elem in hyperlinks:
                # Find the index of this hyperlink in the paragraph's children
                elem_index = -1
                try:
                    elem_index = children.index(hyperlink_elem)
                except ValueError:
                    # Hyperlink is not a direct child, find its ancestor that is
                    for idx, child in enumerate(children):
                        if hyperlink_elem in child.iter():
                            elem_index = idx
                            break

                if hyperlink_elem.tag != qn("w:hyperlink"):
                    continue

                anchor = hyperlink_elem.get(qn('w:anchor'))
                if not anchor:
                    continue

                # Check if this looks like a pandoc-crossref anchor
                if not (anchor.startswith('fig:') or anchor.startswith('tbl:') or anchor.startswith('eq:')):
                    continue

                # Extract the text inside the hyperlink
                hyperlink_text = ""
                for text_elem in hyperlink_elem.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                    hyperlink_text += text_elem.text or ""

                # Try to find the target bookmark for this anchor
                info = anchor_to_info.get(anchor)

                if not info:
                    # This hyperlink references something that doesn't have a caption/bookmark yet
                    # Infer the type and label from the anchor prefix, and create a bookmark
                    logger.warning(f"[ReferenceHelper]   Hyperlink {anchor} has no caption bookmark - will auto-register")

                    if anchor.startswith('fig:'):
                        ref_type = ReferenceType.FIGURE
                        semantic_id = anchor[4:]
                        label = "Figure"
                        word_bookmark = self.register_figure(semantic_id)
                    elif anchor.startswith('tbl:'):
                        ref_type = ReferenceType.TABLE
                        semantic_id = anchor[4:]
                        label = "Table"
                        word_bookmark = self.register_table(semantic_id)
                    elif anchor.startswith('eq:'):
                        ref_type = ReferenceType.EQUATION
                        semantic_id = anchor[3:]
                        label = "Eq"
                        word_bookmark = self.register_equation(semantic_id)
                    else:
                        continue
                else:
                    # Use info from the caption we found
                    ref_type = info['ref_type']
                    semantic_id = info['semantic_id']
                    word_bookmark = info['word_bookmark']
                    label = info['label']

                # Look for prefix text in the previous run
                prefix_text = None
                prefix_run_element = None

                if elem_index > 0:
                    prev_child = children[elem_index - 1]
                    if prev_child.tag == qn("w:r"):
                        # Extract text from the run
                        prev_text = ""
                        for text_elem in prev_child.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                            prev_text += text_elem.text or ""

                        # Check if it ends with a prefix pattern (with optional trailing whitespace)
                        prefix_pattern = r'(fig\.|tbl\.|eq\.)\s*$'
                        match = re.search(prefix_pattern, prev_text, re.IGNORECASE)
                        if match:
                            prefix_text = match.group()
                            prefix_run_element = prev_child

                # Create HyperlinkReference object
                hyperlink_ref = HyperlinkReference(
                    paragraph=block,
                    hyperlink_element=hyperlink_elem,
                    anchor=anchor,
                    hyperlink_text=hyperlink_text,
                    ref_type=ref_type,
                    semantic_id=semantic_id,
                    word_bookmark=word_bookmark,
                    label=label,
                    prefix_text=prefix_text,
                    prefix_run_element=prefix_run_element,
                    element_index=elem_index
                )

                hyperlink_refs.append(hyperlink_ref)
                logger.debug(
                    f"[ReferenceHelper]   Found: {anchor} -> {word_bookmark} "
                    f"(label={label}, prefix='{prefix_text}')"
                )

        logger.info(f"[ReferenceHelper] Extracted {len(hyperlink_refs)} hyperlink references")
        return hyperlink_refs

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
        logger.info("[ReferenceHelper] Converting all references to REF fields")

        # Build mapping dictionaries and patterns for all reference types
        ref_configs = []

        # Configure figures
        figure_bookmarks = self.get_all_figure_bookmarks_in_order()
        if figure_bookmarks:
            logger.info(f"[ReferenceHelper] Preparing {len(figure_bookmarks)} figure references")
            fig_items = [item for item in self._all_items if item.ref_type == ReferenceType.FIGURE]
            fig_display_to_idx = {}
            fig_sequential_to_idx = {}
            for idx, item in enumerate(fig_items):
                fig_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    fig_display_to_idx[item.display_number] = idx
                    logger.debug(f"[ReferenceHelper]   Figure #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    logger.debug(f"[ReferenceHelper]   Figure #{idx}: (no display number) -> {item.word_bookmark}")

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
            logger.info(f"[ReferenceHelper] Preparing {len(table_bookmarks)} table references")
            tbl_items = [item for item in self._all_items if item.ref_type == ReferenceType.TABLE]
            tbl_display_to_idx = {}
            tbl_sequential_to_idx = {}
            for idx, item in enumerate(tbl_items):
                tbl_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    tbl_display_to_idx[item.display_number] = idx
                    logger.debug(f"[ReferenceHelper]   Table #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    logger.debug(f"[ReferenceHelper]   Table #{idx}: (no display number) -> {item.word_bookmark}")

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
            logger.info(f"[ReferenceHelper] Preparing {len(equation_bookmarks)} equation references")
            eq_items = [item for item in self._all_items if item.ref_type == ReferenceType.EQUATION]
            eq_display_to_idx = {}
            eq_sequential_to_idx = {}
            for idx, item in enumerate(eq_items):
                eq_sequential_to_idx[str(idx + 1)] = idx
                if item.display_number:
                    eq_display_to_idx[item.display_number] = idx
                    logger.debug(f"[ReferenceHelper]   Eq #{idx}: {item.display_number} -> {item.word_bookmark}")
                else:
                    logger.debug(f"[ReferenceHelper]   Eq #{idx}: (no display number) -> {item.word_bookmark}")

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
            logger.debug(f"[ReferenceHelper] Processing paragraph: {paragraph_text[:80]}")
            self._process_paragraph_all_refs(block, ref_configs)
            processed_count += 1

        logger.info(f"[ReferenceHelper] Conversion complete: {processed_count} paragraphs processed")

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

        logger.debug(f"[ReferenceHelper]   Found {len(non_overlapping)} reference(s)")

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
                logger.debug(f"[ReferenceHelper]     {label} '{num_str}' matched display number -> index {bookmark_idx}")
            elif num_str in sequential_to_idx:
                bookmark_idx = sequential_to_idx[num_str]
                logger.debug(f"[ReferenceHelper]     {label} '{num_str}' matched sequential number -> index {bookmark_idx}")
            else:
                logger.warning(f"[ReferenceHelper]     WARNING: No mapping for {label} '{num_str}', skipping")
                continue

            # Get the bookmark name
            if 0 <= bookmark_idx < len(bookmarks):
                bookmark_name = bookmarks[bookmark_idx]
            else:
                logger.warning(f"[ReferenceHelper]     WARNING: Index {bookmark_idx} out of range (max {len(bookmarks) - 1})")
                continue

            # Add text before the reference
            if match.start() > last_pos:
                before_text = original_text[last_pos : match.start()]
                create_text_run(p_element, before_text)

            # Add REF field
            create_ref_field_runs(p_element, bookmark_name, label=label)
            ref_fields_added += 1
            logger.debug(f"[ReferenceHelper]     Added {label} REF field: '{num_str}' -> bookmark '{bookmark_name}'")

            last_pos = match.end()

        # Add remaining text after the last reference
        if last_pos < len(original_text):
            after_text = original_text[last_pos:]
            create_text_run(p_element, after_text)

        logger.debug(f"[ReferenceHelper]   Completed: {ref_fields_added} REF field(s) added")

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

    def convert_all_references_by_hyperlinks(self, document):
        """Convert hyperlink-based references to REF fields in the document.

        This method uses the hyperlinks created by pandoc-crossref (when linkReferences: true)
        instead of regex pattern matching. It's more robust because it directly identifies
        cross-references by their hyperlink anchors pointing to bookmarks.

        Args:
            document: The Word document to process
        """
        logger.info("[ReferenceHelper] Converting hyperlink-based references to REF fields")

        # Build mapping from semantic IDs (e.g., "fig:test_figure") to Word bookmarks
        semantic_to_word_bookmark = {}
        semantic_to_label = {}

        for item in self._all_items:
            # Pandoc-crossref uses "fig:id", "tbl:id", "eq:id" format
            if item.ref_type == ReferenceType.FIGURE:
                semantic_key = f"fig:{item.semantic_id}"
                label = "Figure"
            elif item.ref_type == ReferenceType.TABLE:
                semantic_key = f"tbl:{item.semantic_id}"
                label = "Table"
            elif item.ref_type == ReferenceType.EQUATION:
                semantic_key = f"eq:{item.semantic_id}"
                label = "Eq"
            else:
                continue

            semantic_to_word_bookmark[semantic_key] = item.word_bookmark
            semantic_to_label[semantic_key] = label
            logger.debug(f"[ReferenceHelper]   Mapped '{semantic_key}' -> '{item.word_bookmark}' ({label})")

        # Skip caption paragraphs
        caption_styles = {"Image Caption", "Table Caption", "Captioned Figure"}

        # Process all paragraphs looking for hyperlinks
        processed_count = 0
        hyperlink_count = 0

        for block in iter_block_items(document):
            if not isinstance(block, Paragraph):
                continue

            # Skip caption paragraphs
            if block.style.name in caption_styles:
                continue

            p_element = block._p

            # Look for hyperlink elements with anchors
            hyperlinks = p_element.findall('.//w:hyperlink', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

            if not hyperlinks:
                continue

            # Check if any hyperlinks point to our registered references
            has_matching_refs = False
            for hyperlink in hyperlinks:
                anchor = hyperlink.get(qn('w:anchor'))
                if anchor and anchor in semantic_to_word_bookmark:
                    has_matching_refs = True
                    break

            if not has_matching_refs:
                continue

            # Process this paragraph to replace hyperlinks with REF fields
            logger.debug(f"[ReferenceHelper] Processing paragraph: {block.text[:80]}")
            refs_converted = self._process_paragraph_hyperlinks(block, semantic_to_word_bookmark, semantic_to_label)
            if refs_converted > 0:
                processed_count += 1
                hyperlink_count += refs_converted

        logger.info(f"[ReferenceHelper] Conversion complete: {processed_count} paragraphs processed, {hyperlink_count} hyperlinks converted")

    def _process_paragraph_hyperlinks(self, paragraph: Paragraph, semantic_to_word_bookmark: Dict[str, str], semantic_to_label: Dict[str, str]) -> int:
        """Process a paragraph to replace hyperlinks with REF fields.

        Args:
            paragraph: The paragraph to process
            semantic_to_word_bookmark: Mapping from semantic IDs to Word bookmarks
            semantic_to_label: Mapping from semantic IDs to labels (Figure, Table, Eq)

        Returns:
            Number of hyperlinks converted
        """
        p_element = paragraph._p

        # Build a list of all child elements in order, tracking which are hyperlinks
        # and what their positions are
        elements_info = []

        for child in p_element:
            if child.tag == qn("w:hyperlink"):
                anchor = child.get(qn('w:anchor'))
                if anchor and anchor in semantic_to_word_bookmark:
                    # This is a reference hyperlink we need to convert
                    # Extract the text from the hyperlink
                    hyperlink_text = ""
                    for text_elem in child.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                        hyperlink_text += text_elem.text or ""

                    elements_info.append({
                        'type': 'ref_hyperlink',
                        'element': child,
                        'anchor': anchor,
                        'text': hyperlink_text
                    })
                else:
                    # Regular hyperlink, keep as-is
                    elements_info.append({
                        'type': 'hyperlink',
                        'element': child
                    })
            elif child.tag == qn("w:r"):
                # Regular run with text
                text_content = ""
                for text_elem in child.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                    text_content += text_elem.text or ""

                elements_info.append({
                    'type': 'run',
                    'element': child,
                    'text': text_content
                })
            else:
                # Other element (bookmarkStart, bookmarkEnd, etc.), keep as-is
                elements_info.append({
                    'type': 'other',
                    'element': child
                })

        # Check if there are any ref_hyperlinks to convert
        has_refs = any(elem['type'] == 'ref_hyperlink' for elem in elements_info)
        if not has_refs:
            return 0

        # Clear the paragraph
        for child in list(p_element):
            p_element.remove(child)

        # Rebuild the paragraph, converting ref_hyperlinks to REF fields
        # and removing the prefix text before each hyperlink
        refs_converted = 0

        # Pre-process to mark runs that need prefix removal
        for i, elem_info in enumerate(elements_info):
            if elem_info['type'] == 'ref_hyperlink':
                # Check if the previous element is a run with prefix text
                # Pandoc-crossref creates text like "fig." or "tbl." or "eq." before the hyperlink
                if i > 0 and elements_info[i-1]['type'] == 'run':
                    prev_text = elements_info[i-1].get('text', '')
                    # Remove prefix patterns like "fig.", "tbl.", "eq." at the end of the previous run
                    # Note: pandoc-crossref uses lowercase abbreviations
                    prefix_pattern = r'(fig\.|tbl\.|eq\.)$'
                    match = re.search(prefix_pattern, prev_text, re.IGNORECASE)
                    if match:
                        # Mark this run as having its suffix removed
                        new_text = re.sub(prefix_pattern, '', prev_text, flags=re.IGNORECASE)
                        elements_info[i-1]['text'] = new_text
                        elements_info[i-1]['prefix_removed'] = True

        # Now rebuild the paragraph
        for i, elem_info in enumerate(elements_info):
            if elem_info['type'] == 'ref_hyperlink':
                # Convert to REF field
                anchor = elem_info['anchor']
                word_bookmark = semantic_to_word_bookmark[anchor]
                label = semantic_to_label[anchor]

                create_ref_field_runs(p_element, word_bookmark, label=label)
                refs_converted += 1
                logger.debug(f"[ReferenceHelper]     Converted hyperlink '{anchor}' -> REF field '{word_bookmark}' ({label})")

            elif elem_info['type'] == 'hyperlink':
                # Keep regular hyperlink as-is
                p_element.append(elem_info['element'])

            elif elem_info['type'] == 'run':
                # Check if we modified the text
                if elem_info.get('prefix_removed'):
                    # Create a new run with the modified text
                    new_text = elem_info['text']
                    if new_text:  # Only add if there's still text left
                        create_text_run(p_element, new_text)
                else:
                    # Keep run as-is
                    p_element.append(elem_info['element'])

            else:
                # Keep other elements as-is
                p_element.append(elem_info['element'])

        return refs_converted

    def convert_hyperlink_references(self, hyperlink_refs: List[HyperlinkReference]):
        """Convert a list of hyperlink references to REF fields.

        This method is a slot-in replacement for convert_all_references that operates
        on a pre-extracted list of HyperlinkReference objects. This provides more control
        and efficiency when you already have the references extracted.

        Args:
            hyperlink_refs: List of HyperlinkReference objects to convert
        """
        logger.info(f"[ReferenceHelper] Converting {len(hyperlink_refs)} hyperlink references to REF fields")

        # Group references by paragraph to process them efficiently
        from collections import defaultdict
        refs_by_paragraph = defaultdict(list)

        for ref in hyperlink_refs:
            refs_by_paragraph[id(ref.paragraph)].append(ref)

        processed_count = 0
        total_converted = 0

        for para_id, para_refs in refs_by_paragraph.items():
            # Sort by element_index in reverse order so we can process from end to start
            # This prevents index shifting issues when removing elements
            para_refs.sort(key=lambda r: r.element_index, reverse=True)

            # Get the paragraph element
            paragraph = para_refs[0].paragraph
            p_element = paragraph._p

            logger.debug(f"[ReferenceHelper] Processing paragraph with {len(para_refs)} reference(s): {paragraph.text[:80]}")

            # Build a list of all child elements
            children = list(p_element)

            # Create a reconstruction plan
            reconstruction_plan = []
            elements_to_remove = set()

            for ref in para_refs:
                # Mark hyperlink element for removal
                elements_to_remove.add(id(ref.hyperlink_element))

                # Mark prefix run for removal if it exists
                if ref.prefix_run_element is not None:
                    elements_to_remove.add(id(ref.prefix_run_element))

            # Build reconstruction plan by scanning all children
            for idx, child in enumerate(children):
                child_id = id(child)

                # Check if this is a hyperlink we're converting
                ref_for_this = None
                for ref in para_refs:
                    if id(ref.hyperlink_element) == child_id:
                        ref_for_this = ref
                        break

                if ref_for_this:
                    # This hyperlink needs to be converted to a REF field
                    reconstruction_plan.append({
                        'type': 'ref_field',
                        'word_bookmark': ref_for_this.word_bookmark,
                        'label': ref_for_this.label
                    })
                elif child_id in elements_to_remove:
                    # This is a prefix run that should be removed
                    # But we need to check if there's any text after the prefix
                    if child.tag == qn("w:r"):
                        # Extract text from the run
                        run_text = ""
                        for text_elem in child.findall('.//w:t', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
                            run_text += text_elem.text or ""

                        # Remove the prefix pattern
                        for ref in para_refs:
                            if ref.prefix_run_element is not None and id(ref.prefix_run_element) == child_id:
                                if ref.prefix_text:
                                    # Remove the prefix text from the run
                                    remaining_text = run_text[:-len(ref.prefix_text)]
                                    if remaining_text:
                                        reconstruction_plan.append({
                                            'type': 'text',
                                            'text': remaining_text
                                        })
                                break
                else:
                    # Keep this element as-is
                    reconstruction_plan.append({
                        'type': 'element',
                        'element': child
                    })

            # Clear the paragraph
            for child in list(p_element):
                p_element.remove(child)

            # Rebuild the paragraph according to the plan
            refs_converted = 0
            for item in reconstruction_plan:
                if item['type'] == 'ref_field':
                    create_ref_field_runs(p_element, item['word_bookmark'], label=item['label'])
                    refs_converted += 1
                    logger.debug(f"[ReferenceHelper]     Added REF field: {item['label']} -> bookmark '{item['word_bookmark']}'")
                elif item['type'] == 'text':
                    create_text_run(p_element, item['text'])
                elif item['type'] == 'element':
                    p_element.append(item['element'])

            processed_count += 1
            total_converted += refs_converted

        logger.info(f"[ReferenceHelper] Conversion complete: {processed_count} paragraphs processed, {total_converted} references converted")

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
