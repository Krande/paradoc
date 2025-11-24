"""Extract cross-reference information from markdown AST.

This module provides a CrossRefExtractor that analyzes Pandoc AST JSON to extract
all instances of figures, tables, equations and their cross-references. This data
can be used later to verify that exported documents (e.g., .docx) have properly
updated all cross-references.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RefType(Enum):
    """Types of cross-referenceable items."""

    FIGURE = "fig"
    TABLE = "tbl"
    EQUATION = "eq"


@dataclass
class RefTarget:
    """A cross-reference target (figure, table, or equation).

    Attributes:
        ref_type: Type of reference (FIGURE, TABLE, EQUATION)
        ref_id: The semantic identifier (e.g., "historical_trends" from "fig:historical_trends")
        full_id: The full identifier with prefix (e.g., "fig:historical_trends")
        caption_text: The caption text (if available)
        source_file: The source markdown file this target was defined in
        ast_block: The AST block containing this target (for debugging)
    """

    ref_type: RefType
    ref_id: str
    full_id: str
    caption_text: Optional[str] = None
    source_file: Optional[str] = None
    ast_block: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        return f"RefTarget({self.full_id}, caption='{self.caption_text[:40] if self.caption_text else None}...')"


@dataclass
class RefCitation:
    """A cross-reference citation/usage.

    Attributes:
        ref_type: Type of reference being cited
        ref_id: The semantic identifier being referenced
        full_id: The full identifier with prefix
        context_text: Surrounding text context (paragraph containing the reference)
        source_file: The source markdown file this citation appears in
        ast_inline: The AST inline element containing this citation (for debugging)
    """

    ref_type: RefType
    ref_id: str
    full_id: str
    context_text: Optional[str] = None
    source_file: Optional[str] = None
    ast_inline: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        ctx = self.context_text[:60] if self.context_text else None
        return f"RefCitation({self.full_id}, context='{ctx}...')"


@dataclass
class CrossRefData:
    """Complete cross-reference data extracted from a document.

    Attributes:
        targets: All cross-reference targets (figures, tables, equations) by full_id
        citations: All cross-reference citations/usages
        figures: All figure targets by ref_id
        tables: All table targets by ref_id
        equations: All equation targets by ref_id
        dangling_citations: Citations that reference non-existent targets
    """

    targets: Dict[str, RefTarget] = field(default_factory=dict)
    citations: List[RefCitation] = field(default_factory=list)
    figures: Dict[str, RefTarget] = field(default_factory=dict)
    tables: Dict[str, RefTarget] = field(default_factory=dict)
    equations: Dict[str, RefTarget] = field(default_factory=dict)
    dangling_citations: List[RefCitation] = field(default_factory=list)

    def get_target(self, full_id: str) -> Optional[RefTarget]:
        """Get a target by its full ID (e.g., 'fig:historical_trends')."""
        return self.targets.get(full_id)

    def get_citations_for_target(self, full_id: str) -> List[RefCitation]:
        """Get all citations that reference a specific target."""
        return [c for c in self.citations if c.full_id == full_id]

    def validate(self) -> Dict[str, Any]:
        """Validate the cross-reference data and return statistics.

        Returns:
            Dictionary with validation results and statistics
        """
        stats = {
            "total_targets": len(self.targets),
            "total_citations": len(self.citations),
            "figures": len(self.figures),
            "tables": len(self.tables),
            "equations": len(self.equations),
            "dangling_citations": len(self.dangling_citations),
            "unreferenced_targets": [],
            "citation_counts": {},
        }

        # Find unreferenced targets
        referenced_ids = {c.full_id for c in self.citations}
        for full_id, target in self.targets.items():
            if full_id not in referenced_ids:
                stats["unreferenced_targets"].append(full_id)

        # Count citations per target
        for citation in self.citations:
            stats["citation_counts"][citation.full_id] = stats["citation_counts"].get(citation.full_id, 0) + 1

        return stats

    def __repr__(self) -> str:
        return (
            f"CrossRefData(targets={len(self.targets)}, citations={len(self.citations)}, "
            f"figures={len(self.figures)}, tables={len(self.tables)}, equations={len(self.equations)})"
        )


class CrossRefExtractor:
    """Extract cross-reference information from Pandoc AST.

    This class analyzes a Pandoc AST JSON structure to find all:
    - Figure definitions (with IDs like 'fig:name')
    - Table definitions (with IDs like 'tbl:name')
    - Equation definitions (with IDs like 'eq:name')
    - Cross-reference citations ([@fig:name], [@tbl:name], [@eq:name])

    Usage:
        extractor = CrossRefExtractor(ast_dict)
        data = extractor.extract()

        # Validate and get statistics
        stats = data.validate()
        print(f"Found {stats['total_targets']} targets and {stats['total_citations']} citations")

        # Check for problems
        if data.dangling_citations:
            print(f"Warning: {len(data.dangling_citations)} citations reference non-existent targets")
    """

    def __init__(self, ast: Dict[str, Any]):
        """Initialize with a Pandoc AST dictionary.

        Args:
            ast: Pandoc AST as a dictionary (from json.loads of pandoc --to=json output)
        """
        self.ast = ast
        self.current_source_file: Optional[str] = None

    def extract(self) -> CrossRefData:
        """Extract all cross-reference data from the AST.

        Returns:
            CrossRefData object containing all targets and citations
        """
        data = CrossRefData()

        blocks = self.ast.get("blocks", [])
        self._extract_from_blocks(blocks, data)

        # Identify dangling citations
        target_ids = set(data.targets.keys())
        for citation in data.citations:
            if citation.full_id not in target_ids:
                data.dangling_citations.append(citation)

        return data

    def _extract_from_blocks(self, blocks: List[Dict[str, Any]], data: CrossRefData):
        """Recursively extract references from block elements."""
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get("t")

            # Check for source file markers
            if block_type == "RawBlock":
                self._check_source_marker(block)

            # Extract targets from different block types
            if block_type == "Figure":
                self._extract_figure_target(block, data)
            elif block_type == "Table":
                self._extract_table_target(block, data)
            elif block_type == "Div":
                self._extract_div_target(block, data)
            elif block_type in ["Para", "Plain"]:
                # Extract citations from paragraph inlines
                inlines = block.get("c", [])
                if isinstance(inlines, list):
                    context_text = self._extract_text_from_inlines(inlines)
                    self._extract_from_inlines(inlines, data, context_text)
                    # Also check for equation targets in Span elements within paragraphs
                    self._extract_equation_targets_from_inlines(inlines, data)

            # Recursively process nested blocks
            if "c" in block:
                self._process_nested_content(block["c"], data)

    def _check_source_marker(self, block: Dict[str, Any]):
        """Check if this raw block is a source file marker."""
        content = block.get("c", [])
        if len(content) >= 2:
            # RawBlock has format: ["html", "<!-- PARADOC_SOURCE_FILE: path -->"]
            text = content[1] if isinstance(content[1], str) else ""
            match = re.search(r"PARADOC_SOURCE_FILE:\s*(.+?)\s*-->", text)
            if match:
                self.current_source_file = match.group(1)

    def _extract_figure_target(self, block: Dict[str, Any], data: CrossRefData):
        """Extract figure target from a Figure block."""
        content = block.get("c", [])
        if len(content) >= 1:
            attrs = content[0]
            fig_id = self._extract_id_from_attrs(attrs)

            if fig_id and (fig_id.startswith("fig:") or fig_id.startswith("fig_")):
                # Normalize ID (pandoc converts hyphens to underscores)
                normalized_id = fig_id.replace("_", ":") if ":" not in fig_id else fig_id

                # Extract caption if available
                caption_text = None
                if len(content) >= 2:
                    caption_content = content[1]
                    if isinstance(caption_content, dict) and caption_content.get("t") == "Caption":
                        caption_blocks = (
                            caption_content.get("c", [[]])[1] if len(caption_content.get("c", [])) > 1 else []
                        )
                        caption_text = self._extract_text_from_blocks(caption_blocks)

                ref_id = normalized_id.split(":", 1)[1] if ":" in normalized_id else normalized_id.split("_", 1)[1]

                target = RefTarget(
                    ref_type=RefType.FIGURE,
                    ref_id=ref_id,
                    full_id=normalized_id,
                    caption_text=caption_text,
                    source_file=self.current_source_file,
                    ast_block=block,
                )

                data.targets[normalized_id] = target
                data.figures[ref_id] = target

    def _extract_table_target(self, block: Dict[str, Any], data: CrossRefData):
        """Extract table target from a Table block."""
        content = block.get("c", [])
        if len(content) >= 1:
            attrs = content[0]
            tbl_id = self._extract_id_from_attrs(attrs)

            if tbl_id and (tbl_id.startswith("tbl:") or tbl_id.startswith("tbl_")):
                # Normalize ID
                normalized_id = tbl_id.replace("_", ":") if ":" not in tbl_id else tbl_id

                # Extract caption if available
                caption_text = None
                if len(content) >= 2:
                    caption_content = content[1]
                    if isinstance(caption_content, dict) and caption_content.get("t") == "Caption":
                        caption_blocks = (
                            caption_content.get("c", [[]])[1] if len(caption_content.get("c", [])) > 1 else []
                        )
                        caption_text = self._extract_text_from_blocks(caption_blocks)

                ref_id = normalized_id.split(":", 1)[1] if ":" in normalized_id else normalized_id.split("_", 1)[1]

                target = RefTarget(
                    ref_type=RefType.TABLE,
                    ref_id=ref_id,
                    full_id=normalized_id,
                    caption_text=caption_text,
                    source_file=self.current_source_file,
                    ast_block=block,
                )

                data.targets[normalized_id] = target
                data.tables[ref_id] = target

    def _extract_div_target(self, block: Dict[str, Any], data: CrossRefData):
        """Extract targets from Div blocks (pandoc-crossref wraps items in Divs)."""
        content = block.get("c", [])
        if len(content) >= 1:
            attrs = content[0]
            div_id = self._extract_id_from_attrs(attrs)

            # Check if this Div has a figure/table/equation ID
            if div_id:
                ref_type = None
                if div_id.startswith("fig:") or div_id.startswith("fig_"):
                    ref_type = RefType.FIGURE
                elif div_id.startswith("tbl:") or div_id.startswith("tbl_"):
                    ref_type = RefType.TABLE
                elif div_id.startswith("eq:") or div_id.startswith("eq_"):
                    ref_type = RefType.EQUATION

                if ref_type:
                    # Normalize ID
                    normalized_id = div_id.replace("_", ":") if ":" not in div_id else div_id
                    ref_id = normalized_id.split(":", 1)[1] if ":" in normalized_id else normalized_id.split("_", 1)[1]

                    # Extract caption/content text
                    caption_text = None
                    if len(content) >= 2:
                        nested_blocks = content[1] if isinstance(content[1], list) else []
                        caption_text = self._extract_text_from_blocks(nested_blocks)

                    target = RefTarget(
                        ref_type=ref_type,
                        ref_id=ref_id,
                        full_id=normalized_id,
                        caption_text=caption_text,
                        source_file=self.current_source_file,
                        ast_block=block,
                    )

                    data.targets[normalized_id] = target

                    if ref_type == RefType.FIGURE:
                        data.figures[ref_id] = target
                    elif ref_type == RefType.TABLE:
                        data.tables[ref_id] = target
                    elif ref_type == RefType.EQUATION:
                        data.equations[ref_id] = target

    def _extract_equation_targets_from_inlines(self, inlines: List[Any], data: CrossRefData):
        """Extract equation targets from Span inline elements.

        Pandoc-crossref processes equations like $$E=mc^2$$ {#eq:energy} into
        Span elements with the equation ID and containing Math elements.

        Example structure:
        {'t': 'Span', 'c': [['eq:energy', [], []], [{'t': 'Math', 'c': [...]}]]}
        """
        for inline in inlines:
            if not isinstance(inline, dict):
                continue

            inline_type = inline.get("t")

            if inline_type == "Span":
                content = inline.get("c", [])
                if len(content) >= 2:
                    attrs = content[0]
                    span_id = self._extract_id_from_attrs(attrs)

                    # Check if this is an equation ID
                    if span_id and (span_id.startswith("eq:") or span_id.startswith("eq_")):
                        # Normalize ID
                        normalized_id = span_id.replace("_", ":") if ":" not in span_id else span_id
                        ref_id = (
                            normalized_id.split(":", 1)[1] if ":" in normalized_id else normalized_id.split("_", 1)[1]
                        )

                        # Extract equation content (the Math element contains the LaTeX)
                        equation_content = None
                        nested_inlines = content[1] if isinstance(content[1], list) else []
                        for nested in nested_inlines:
                            if isinstance(nested, dict) and nested.get("t") == "Math":
                                # Math element format: {'t': 'Math', 'c': [{'t': 'DisplayMath'}, 'latex_string']}
                                math_content = nested.get("c", [])
                                if len(math_content) >= 2:
                                    equation_content = math_content[1]  # The LaTeX string
                                break

                        target = RefTarget(
                            ref_type=RefType.EQUATION,
                            ref_id=ref_id,
                            full_id=normalized_id,
                            caption_text=equation_content,  # Store the LaTeX as "caption"
                            source_file=self.current_source_file,
                            ast_block=inline,
                        )

                        data.targets[normalized_id] = target
                        data.equations[ref_id] = target

            # Recursively check nested inlines
            if "c" in inline:
                content = inline["c"]
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, list):
                            self._extract_equation_targets_from_inlines(item, data)

    def _extract_from_inlines(self, inlines: List[Any], data: CrossRefData, context_text: Optional[str] = None):
        """Recursively extract citations from inline elements."""
        for inline in inlines:
            if not isinstance(inline, dict):
                continue

            inline_type = inline.get("t")

            # Look for Cite elements (cross-references)
            if inline_type == "Cite":
                self._extract_citation(inline, data, context_text)

            # Look for Link elements with anchors (alternative cross-ref format)
            elif inline_type == "Link":
                self._extract_link_citation(inline, data, context_text)

            # Recursively process nested inlines
            if "c" in inline:
                content = inline["c"]
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, list):
                            self._extract_from_inlines(item, data, context_text)

    def _extract_citation(self, inline: Dict[str, Any], data: CrossRefData, context_text: Optional[str] = None):
        """Extract citation from a Cite inline element."""
        content = inline.get("c", [])
        if len(content) >= 1:
            citations = content[0]
            if isinstance(citations, list):
                for citation in citations:
                    if isinstance(citation, dict):
                        citation_id = citation.get("citationId", "")

                        # Check if this is a cross-reference citation
                        ref_type = None
                        if citation_id.startswith("fig:") or citation_id.startswith("fig_"):
                            ref_type = RefType.FIGURE
                        elif citation_id.startswith("tbl:") or citation_id.startswith("tbl_"):
                            ref_type = RefType.TABLE
                        elif citation_id.startswith("eq:") or citation_id.startswith("eq_"):
                            ref_type = RefType.EQUATION

                        if ref_type:
                            # Normalize ID
                            normalized_id = citation_id.replace("_", ":") if ":" not in citation_id else citation_id
                            ref_id = (
                                normalized_id.split(":", 1)[1]
                                if ":" in normalized_id
                                else normalized_id.split("_", 1)[1]
                            )

                            cite = RefCitation(
                                ref_type=ref_type,
                                ref_id=ref_id,
                                full_id=normalized_id,
                                context_text=context_text,
                                source_file=self.current_source_file,
                                ast_inline=inline,
                            )

                            data.citations.append(cite)

    def _extract_link_citation(self, inline: Dict[str, Any], data: CrossRefData, context_text: Optional[str] = None):
        """Extract citation from a Link inline element (hyperlink format)."""
        content = inline.get("c", [])
        if len(content) >= 3:
            # Link format: [attrs, [inlines], [url, title]]
            target = content[2]
            if isinstance(target, list) and len(target) >= 1:
                url = target[0]

                # Check if this is an anchor link to a cross-reference
                if isinstance(url, str) and url.startswith("#"):
                    anchor = url[1:]  # Remove '#'

                    ref_type = None
                    if anchor.startswith("fig:") or anchor.startswith("fig_"):
                        ref_type = RefType.FIGURE
                    elif anchor.startswith("tbl:") or anchor.startswith("tbl_"):
                        ref_type = RefType.TABLE
                    elif anchor.startswith("eq:") or anchor.startswith("eq_"):
                        ref_type = RefType.EQUATION

                    if ref_type:
                        # Normalize ID
                        normalized_id = anchor.replace("_", ":") if ":" not in anchor else anchor
                        ref_id = (
                            normalized_id.split(":", 1)[1] if ":" in normalized_id else normalized_id.split("_", 1)[1]
                        )

                        cite = RefCitation(
                            ref_type=ref_type,
                            ref_id=ref_id,
                            full_id=normalized_id,
                            context_text=context_text,
                            source_file=self.current_source_file,
                            ast_inline=inline,
                        )

                        data.citations.append(cite)

    def _process_nested_content(self, content: Any, data: CrossRefData):
        """Process potentially nested content recursively."""
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # Check if this dict has blocks
                    if "blocks" in item:
                        self._extract_from_blocks(item["blocks"], data)
                    # Or if it's itself a block
                    elif "t" in item:
                        self._extract_from_blocks([item], data)
                elif isinstance(item, list):
                    # Nested list of blocks
                    self._extract_from_blocks(item, data)

    def _extract_id_from_attrs(self, attrs: Any) -> str:
        """Extract ID from Pandoc Attr structure.

        Pandoc Attr can be:
        - A dict with 'id' key
        - A list [id, [classes], {attributes}]
        """
        if isinstance(attrs, dict):
            return attrs.get("id", "")
        elif isinstance(attrs, list) and len(attrs) >= 1:
            return attrs[0] if isinstance(attrs[0], str) else ""
        return ""

    def _extract_text_from_blocks(self, blocks: List[Any]) -> str:
        """Extract plain text from a list of block elements."""
        text_parts = []
        for block in blocks:
            if isinstance(block, dict):
                if block.get("t") in ["Para", "Plain"]:
                    inlines = block.get("c", [])
                    text_parts.append(self._extract_text_from_inlines(inlines))
                elif block.get("t") == "Str":
                    text_parts.append(block.get("c", ""))
        return " ".join(text_parts).strip()

    def _extract_text_from_inlines(self, inlines: List[Any]) -> str:
        """Extract plain text from a list of inline elements."""
        text_parts = []
        for inline in inlines:
            if isinstance(inline, dict):
                inline_type = inline.get("t")
                if inline_type == "Str":
                    text_parts.append(inline.get("c", ""))
                elif inline_type == "Space":
                    text_parts.append(" ")
                elif inline_type in ["Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps"]:
                    nested = inline.get("c", [])
                    text_parts.append(self._extract_text_from_inlines(nested))
                elif inline_type == "Span":
                    content = inline.get("c", [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
                elif inline_type == "Link":
                    content = inline.get("c", [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
                elif inline_type == "Cite":
                    content = inline.get("c", [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
        return "".join(text_parts).strip()
