"""Extract document structure and section hierarchy from Pandoc AST.

This module provides comprehensive document structure extraction including:
- Section hierarchy with navigation (parent, children, siblings)
- Paragraph content within sections
- Figures, tables, and equations within sections
- Cross-references within sections
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContentType(Enum):
    """Types of content elements in the document."""
    PARAGRAPH = "paragraph"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    LIST = "list"
    CODE_BLOCK = "code_block"
    QUOTE = "quote"
    RAW = "raw"


class Paragraph(BaseModel):
    """A paragraph in the document.

    Attributes:
        text: Plain text content of the paragraph
        ast_block: The original AST block (for debugging)
        source_file: Source markdown file this paragraph came from
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str
    ast_block: Optional[Dict[str, Any]] = None
    source_file: Optional[str] = None


class FigureRef(BaseModel):
    """Reference to a figure within a section.

    Attributes:
        ref_id: The semantic identifier (e.g., "historical_trends")
        full_id: The full identifier with prefix (e.g., "fig:historical_trends")
        caption: The caption text (if available)
        source_file: Source markdown file
    """
    ref_id: str
    full_id: str
    caption: Optional[str] = None
    source_file: Optional[str] = None


class TableRef(BaseModel):
    """Reference to a table within a section.

    Attributes:
        ref_id: The semantic identifier
        full_id: The full identifier with prefix (e.g., "tbl:current_metrics")
        caption: The caption text (if available)
        source_file: Source markdown file
    """
    ref_id: str
    full_id: str
    caption: Optional[str] = None
    source_file: Optional[str] = None


class EquationRef(BaseModel):
    """Reference to an equation within a section.

    Attributes:
        ref_id: The semantic identifier
        full_id: The full identifier with prefix (e.g., "eq:energy")
        latex: The LaTeX content (if available)
        source_file: Source markdown file
    """
    ref_id: str
    full_id: str
    latex: Optional[str] = None
    source_file: Optional[str] = None


class CrossReferenceUsage(BaseModel):
    """A cross-reference usage (citation) within a section.

    Attributes:
        target_id: The full ID of the target being referenced
        target_type: Type of target (fig, tbl, eq)
        context: Surrounding text context
        source_file: Source markdown file
    """
    target_id: str
    target_type: str
    context: Optional[str] = None
    source_file: Optional[str] = None


class Section(BaseModel):
    """A section in the document hierarchy.

    Attributes:
        id: Unique identifier for this section
        title: Section title text
        level: Heading level (1-6)
        number: Numeric index (e.g., "1.2.3", "A.1", "B.2.1")
        paragraphs: List of paragraphs in this section
        figures: List of figures defined in this section
        tables: List of tables defined in this section
        equations: List of equations defined in this section
        cross_references: List of cross-reference usages in this section
        parent: Reference to parent section (None for top-level)
        children: List of child sections
        previous_sibling: Previous section at the same level
        next_sibling: Next section at the same level
        source_file: Source markdown file
        is_appendix: Whether this section is in the appendix
        ast_block: The original AST Header block
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    title: str
    level: int
    number: str
    paragraphs: List[Paragraph] = Field(default_factory=list)
    figures: List[FigureRef] = Field(default_factory=list)
    tables: List[TableRef] = Field(default_factory=list)
    equations: List[EquationRef] = Field(default_factory=list)
    cross_references: List[CrossReferenceUsage] = Field(default_factory=list)
    parent: Optional[Section] = None
    children: List[Section] = Field(default_factory=list)
    previous_sibling: Optional[Section] = None
    next_sibling: Optional[Section] = None
    source_file: Optional[str] = None
    is_appendix: bool = False
    ast_block: Optional[Dict[str, Any]] = None

    def get_all_descendants(self) -> List[Section]:
        """Get all descendant sections recursively."""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    def get_path(self) -> List[Section]:
        """Get the path from root to this section."""
        path = []
        current = self
        while current:
            path.insert(0, current)
            current = current.parent
        return path

    def get_depth(self) -> int:
        """Get the depth of this section (root is 0)."""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth


class DocumentStructure(BaseModel):
    """Complete document structure with section hierarchy and content.

    Attributes:
        sections: All sections in document order
        root_sections: Top-level sections
        figures: All figures in the document by full_id
        tables: All tables in the document by full_id
        equations: All equations in the document by full_id
        cross_references: All cross-reference usages in the document
        metadata: Document metadata from AST
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    sections: List[Section] = Field(default_factory=list)
    root_sections: List[Section] = Field(default_factory=list)
    figures: Dict[str, FigureRef] = Field(default_factory=dict)
    tables: Dict[str, TableRef] = Field(default_factory=dict)
    equations: Dict[str, EquationRef] = Field(default_factory=dict)
    cross_references: List[CrossReferenceUsage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_section_by_id(self, section_id: str) -> Optional[Section]:
        """Get a section by its ID."""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def get_section_by_number(self, number: str) -> Optional[Section]:
        """Get a section by its number (e.g., '1.2.3', 'A.1')."""
        for section in self.sections:
            if section.number == number:
                return section
        return None

    def get_sections_by_level(self, level: int) -> List[Section]:
        """Get all sections at a specific level."""
        return [s for s in self.sections if s.level == level]

    def get_appendix_sections(self) -> List[Section]:
        """Get all appendix sections."""
        return [s for s in self.sections if s.is_appendix]

    def get_main_sections(self) -> List[Section]:
        """Get all main (non-appendix) sections."""
        return [s for s in self.sections if not s.is_appendix]

    def validate(self) -> Dict[str, Any]:
        """Validate the document structure and return statistics.

        Returns:
            Dictionary with validation results and statistics
        """
        stats = {
            'total_sections': len(self.sections),
            'root_sections': len(self.root_sections),
            'total_figures': len(self.figures),
            'total_tables': len(self.tables),
            'total_equations': len(self.equations),
            'total_cross_references': len(self.cross_references),
            'sections_by_level': {},
            'appendix_sections': len(self.get_appendix_sections()),
            'main_sections': len(self.get_main_sections()),
        }

        # Count sections by level
        for level in range(1, 7):
            count = len(self.get_sections_by_level(level))
            if count > 0:
                stats['sections_by_level'][level] = count

        return stats


class DocumentStructureExtractor:
    """Extract document structure and section hierarchy from Pandoc AST.

    This extractor analyzes the AST to build a complete hierarchical structure
    of the document, including sections, content, and cross-references.

    Usage:
        extractor = DocumentStructureExtractor(ast_dict)
        structure = extractor.extract()

        # Validate and get statistics
        stats = structure.validate()
        print(f"Found {stats['total_sections']} sections")

        # Navigate the hierarchy
        for root_section in structure.root_sections:
            print(f"Section {root_section.number}: {root_section.title}")
            for child in root_section.children:
                print(f"  {child.number}: {child.title}")
    """

    def __init__(self, ast: Dict[str, Any]):
        """Initialize with a Pandoc AST dictionary.

        Args:
            ast: Pandoc AST as a dictionary (from json.loads of pandoc --to=json output)
        """
        self.ast = ast
        self.current_source_file: Optional[str] = None
        self.in_appendix = False
        self.section_counters = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        self.appendix_letter = 64  # ASCII for 'A' - 1
        self.appendix_counters = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}

    def extract(self) -> DocumentStructure:
        """Extract complete document structure from the AST.

        Returns:
            DocumentStructure object containing sections and content
        """
        structure = DocumentStructure()

        # Extract metadata
        structure.metadata = self.ast.get('meta', {})

        # Extract sections and content
        blocks = self.ast.get('blocks', [])
        self._extract_structure(blocks, structure)

        # Build section hierarchy
        self._build_hierarchy(structure)

        # Link siblings
        self._link_siblings(structure)

        return structure

    def _extract_structure(self, blocks: List[Dict[str, Any]], structure: DocumentStructure):
        """Extract sections and content from blocks."""
        current_section: Optional[Section] = None
        section_stack: List[Section] = []

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('t')

            # Check for source file markers
            if block_type == 'RawBlock':
                self._check_source_marker(block)
                # Check for appendix marker
                content = block.get('c', [])
                if len(content) >= 2 and isinstance(content[1], str):
                    if '\\appendix' in content[1]:
                        self.in_appendix = True
                continue

            # Extract header/section
            if block_type == 'Header':
                section = self._extract_section(block)
                if section:
                    structure.sections.append(section)

                    # Update section stack for hierarchy
                    while section_stack and section_stack[-1].level >= section.level:
                        section_stack.pop()

                    section_stack.append(section)
                    current_section = section
                continue

            # Extract content within current section
            if current_section:
                if block_type in ['Para', 'Plain']:
                    paragraph = self._extract_paragraph(block)
                    if paragraph:
                        current_section.paragraphs.append(paragraph)
                        # Extract cross-references from paragraph
                        self._extract_crossrefs_from_block(block, current_section, structure)

                elif block_type == 'Figure':
                    figure = self._extract_figure(block)
                    if figure:
                        current_section.figures.append(figure)
                        structure.figures[figure.full_id] = figure

                elif block_type == 'Table':
                    table = self._extract_table(block)
                    if table:
                        current_section.tables.append(table)
                        structure.tables[table.full_id] = table

                elif block_type == 'Div':
                    # Div blocks can contain figures/tables/equations
                    self._extract_from_div(block, current_section, structure)

                # Extract equations from inline spans in any block
                self._extract_equations_from_block(block, current_section, structure)

    def _check_source_marker(self, block: Dict[str, Any]):
        """Check if this raw block is a source file marker."""
        content = block.get('c', [])
        if len(content) >= 2:
            text = content[1] if isinstance(content[1], str) else ""
            match = re.search(r'PARADOC_SOURCE_FILE:\s*(.+?)\s*-->', text)
            if match:
                self.current_source_file = match.group(1)

    def _extract_section(self, block: Dict[str, Any]) -> Optional[Section]:
        """Extract a section from a Header block."""
        content = block.get('c', [])
        if len(content) < 3:
            return None

        level = content[0]
        attrs = content[1]
        inlines = content[2]

        # Extract section ID and title
        section_id = self._extract_id_from_attrs(attrs)
        title = self._extract_text_from_inlines(inlines)

        # Generate section number
        number = self._generate_section_number(level)

        # Generate ID if not present
        if not section_id:
            section_id = self._title_to_id(title)

        # Get source file from either current_source_file or from AST metadata
        source_file = self.current_source_file
        if not source_file and '_paradoc_source' in block:
            paradoc_source = block['_paradoc_source']
            if isinstance(paradoc_source, dict):
                source_file = paradoc_source.get('source_file')

        section = Section(
            id=section_id,
            title=title,
            level=level,
            number=number,
            source_file=source_file,
            is_appendix=self.in_appendix,
            ast_block=block
        )

        return section

    def _generate_section_number(self, level: int) -> str:
        """Generate section number based on level and current counters."""
        if self.in_appendix:
            # Appendix numbering: A, A.1, A.2, B, B.1, etc.
            if level == 1:
                self.appendix_letter += 1
                self.appendix_counters = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
                return chr(self.appendix_letter)
            else:
                self.appendix_counters[level] += 1
                # Reset deeper levels
                for l in range(level + 1, 7):
                    self.appendix_counters[l] = 0

                parts = [chr(self.appendix_letter)]
                for l in range(2, level + 1):
                    parts.append(str(self.appendix_counters[l]))
                return '.'.join(parts)
        else:
            # Main numbering: 1, 1.1, 1.2, 2, 2.1, etc.
            self.section_counters[level] += 1
            # Reset deeper levels
            for l in range(level + 1, 7):
                self.section_counters[l] = 0

            parts = []
            for l in range(1, level + 1):
                parts.append(str(self.section_counters[l]))
            return '.'.join(parts)

    def _title_to_id(self, title: str) -> str:
        """Convert title to a valid ID."""
        # Convert to lowercase, replace spaces with hyphens
        id_str = title.lower()
        id_str = re.sub(r'[^\w\s-]', '', id_str)
        id_str = re.sub(r'[\s_]+', '-', id_str)
        return id_str

    def _extract_paragraph(self, block: Dict[str, Any]) -> Optional[Paragraph]:
        """Extract a paragraph from a Para or Plain block."""
        inlines = block.get('c', [])
        if not isinstance(inlines, list):
            return None

        text = self._extract_text_from_inlines(inlines)
        if not text.strip():
            return None

        # Get source file from either current_source_file or from AST metadata
        source_file = self.current_source_file
        if not source_file and '_paradoc_source' in block:
            paradoc_source = block['_paradoc_source']
            if isinstance(paradoc_source, dict):
                source_file = paradoc_source.get('source_file')

        return Paragraph(
            text=text,
            ast_block=block,
            source_file=source_file
        )

    def _extract_figure(self, block: Dict[str, Any]) -> Optional[FigureRef]:
        """Extract a figure reference from a Figure block."""
        content = block.get('c', [])
        if len(content) < 1:
            return None

        attrs = content[0]
        fig_id = self._extract_id_from_attrs(attrs)

        if not fig_id or not (fig_id.startswith('fig:') or fig_id.startswith('fig_')):
            return None

        # Normalize ID
        normalized_id = fig_id.replace('_', ':') if ':' not in fig_id else fig_id
        ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

        # Extract caption
        caption = None
        if len(content) >= 2:
            caption_content = content[1]
            if isinstance(caption_content, dict) and caption_content.get('t') == 'Caption':
                caption_blocks = caption_content.get('c', [[]])[1] if len(caption_content.get('c', [])) > 1 else []
                caption = self._extract_text_from_blocks(caption_blocks)

        # Get source file from either current_source_file or from AST metadata
        source_file = self.current_source_file
        if not source_file and '_paradoc_source' in block:
            paradoc_source = block['_paradoc_source']
            if isinstance(paradoc_source, dict):
                source_file = paradoc_source.get('source_file')

        return FigureRef(
            ref_id=ref_id,
            full_id=normalized_id,
            caption=caption,
            source_file=source_file
        )

    def _extract_table(self, block: Dict[str, Any]) -> Optional[TableRef]:
        """Extract a table reference from a Table block."""
        content = block.get('c', [])
        if len(content) < 1:
            return None

        attrs = content[0]
        tbl_id = self._extract_id_from_attrs(attrs)

        if not tbl_id or not (tbl_id.startswith('tbl:') or tbl_id.startswith('tbl_')):
            return None

        # Normalize ID
        normalized_id = tbl_id.replace('_', ':') if ':' not in tbl_id else tbl_id
        ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

        # Extract caption
        caption = None
        if len(content) >= 2:
            caption_content = content[1]
            if isinstance(caption_content, dict) and caption_content.get('t') == 'Caption':
                caption_blocks = caption_content.get('c', [[]])[1] if len(caption_content.get('c', [])) > 1 else []
                caption = self._extract_text_from_blocks(caption_blocks)

        # Get source file from either current_source_file or from AST metadata
        source_file = self.current_source_file
        if not source_file and '_paradoc_source' in block:
            paradoc_source = block['_paradoc_source']
            if isinstance(paradoc_source, dict):
                source_file = paradoc_source.get('source_file')

        return TableRef(
            ref_id=ref_id,
            full_id=normalized_id,
            caption=caption,
            source_file=source_file
        )

    def _extract_from_div(self, block: Dict[str, Any], section: Section, structure: DocumentStructure):
        """Extract content from Div blocks."""
        content = block.get('c', [])
        if len(content) < 1:
            return

        attrs = content[0]
        div_id = self._extract_id_from_attrs(attrs)

        # Get source file from either current_source_file or from AST metadata
        source_file = self.current_source_file
        if not source_file and '_paradoc_source' in block:
            paradoc_source = block['_paradoc_source']
            if isinstance(paradoc_source, dict):
                source_file = paradoc_source.get('source_file')

        # Check if this Div has a figure/table/equation ID
        if div_id:
            if div_id.startswith('fig:') or div_id.startswith('fig_'):
                normalized_id = div_id.replace('_', ':') if ':' not in div_id else div_id
                ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

                caption_text = None
                if len(content) >= 2:
                    nested_blocks = content[1] if isinstance(content[1], list) else []
                    caption_text = self._extract_text_from_blocks(nested_blocks)

                figure = FigureRef(
                    ref_id=ref_id,
                    full_id=normalized_id,
                    caption=caption_text,
                    source_file=source_file
                )
                section.figures.append(figure)
                structure.figures[normalized_id] = figure

            elif div_id.startswith('tbl:') or div_id.startswith('tbl_'):
                normalized_id = div_id.replace('_', ':') if ':' not in div_id else div_id
                ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

                caption_text = None
                if len(content) >= 2:
                    nested_blocks = content[1] if isinstance(content[1], list) else []
                    caption_text = self._extract_text_from_blocks(nested_blocks)

                table = TableRef(
                    ref_id=ref_id,
                    full_id=normalized_id,
                    caption=caption_text,
                    source_file=source_file
                )
                section.tables.append(table)
                structure.tables[normalized_id] = table

            elif div_id.startswith('eq:') or div_id.startswith('eq_'):
                normalized_id = div_id.replace('_', ':') if ':' not in div_id else div_id
                ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

                latex_text = None
                if len(content) >= 2:
                    nested_blocks = content[1] if isinstance(content[1], list) else []
                    latex_text = self._extract_text_from_blocks(nested_blocks)

                equation = EquationRef(
                    ref_id=ref_id,
                    full_id=normalized_id,
                    latex=latex_text,
                    source_file=source_file
                )
                section.equations.append(equation)
                structure.equations[normalized_id] = equation

    def _extract_equations_from_block(self, block: Dict[str, Any], section: Section, structure: DocumentStructure):
        """Extract equations from Span inline elements within a block."""
        # Recursively search for Span elements with equation IDs
        # Pass the block to access its _paradoc_source metadata
        self._find_equation_spans(block, section, structure, block)

    def _find_equation_spans(self, node: Any, section: Section, structure: DocumentStructure, parent_block: Optional[Dict[str, Any]] = None):
        """Recursively find and extract equation Span elements."""
        if isinstance(node, dict):
            if node.get('t') == 'Span':
                content = node.get('c', [])
                if len(content) >= 2:
                    attrs = content[0]
                    span_id = self._extract_id_from_attrs(attrs)

                    if span_id and (span_id.startswith('eq:') or span_id.startswith('eq_')):
                        normalized_id = span_id.replace('_', ':') if ':' not in span_id else span_id
                        ref_id = normalized_id.split(':', 1)[1] if ':' in normalized_id else normalized_id.split('_', 1)[1]

                        # Extract equation content
                        latex_text = None
                        nested_inlines = content[1] if isinstance(content[1], list) else []
                        for nested in nested_inlines:
                            if isinstance(nested, dict) and nested.get('t') == 'Math':
                                math_content = nested.get('c', [])
                                if len(math_content) >= 2:
                                    latex_text = math_content[1]
                                break

                        # Get source file from current_source_file or parent block's metadata
                        source_file = self.current_source_file
                        if not source_file and parent_block and '_paradoc_source' in parent_block:
                            paradoc_source = parent_block['_paradoc_source']
                            if isinstance(paradoc_source, dict):
                                source_file = paradoc_source.get('source_file')

                        equation = EquationRef(
                            ref_id=ref_id,
                            full_id=normalized_id,
                            latex=latex_text,
                            source_file=source_file
                        )
                        section.equations.append(equation)
                        structure.equations[normalized_id] = equation

            # Recurse into all values
            for value in node.values():
                self._find_equation_spans(value, section, structure, parent_block)

        elif isinstance(node, list):
            for item in node:
                self._find_equation_spans(item, section, structure, parent_block)

    def _extract_crossrefs_from_block(self, block: Dict[str, Any], section: Section, structure: DocumentStructure):
        """Extract cross-references from a block."""
        inlines = block.get('c', [])
        if isinstance(inlines, list):
            context_text = self._extract_text_from_inlines(inlines)

            # Get source file from block metadata if available
            source_file = self.current_source_file
            if not source_file and '_paradoc_source' in block:
                paradoc_source = block['_paradoc_source']
                if isinstance(paradoc_source, dict):
                    source_file = paradoc_source.get('source_file')

            self._find_citations(inlines, section, structure, context_text, source_file)

    def _find_citations(self, inlines: List[Any], section: Section, structure: DocumentStructure, context: Optional[str], source_file: Optional[str] = None):
        """Recursively find citation elements in inlines."""
        # Use provided source_file or fall back to current_source_file
        if source_file is None:
            source_file = self.current_source_file

        for inline in inlines:
            if not isinstance(inline, dict):
                continue

            inline_type = inline.get('t')

            if inline_type == 'Cite':
                content = inline.get('c', [])
                if len(content) >= 1:
                    citations = content[0]
                    if isinstance(citations, list):
                        for citation in citations:
                            if isinstance(citation, dict):
                                citation_id = citation.get('citationId', '')

                                # Check if this is a cross-reference
                                target_type = None
                                if citation_id.startswith('fig:') or citation_id.startswith('fig_'):
                                    target_type = 'fig'
                                elif citation_id.startswith('tbl:') or citation_id.startswith('tbl_'):
                                    target_type = 'tbl'
                                elif citation_id.startswith('eq:') or citation_id.startswith('eq_'):
                                    target_type = 'eq'

                                if target_type:
                                    normalized_id = citation_id.replace('_', ':') if ':' not in citation_id else citation_id

                                    crossref = CrossReferenceUsage(
                                        target_id=normalized_id,
                                        target_type=target_type,
                                        context=context,
                                        source_file=source_file
                                    )
                                    section.cross_references.append(crossref)
                                    structure.cross_references.append(crossref)

            elif inline_type == 'Link':
                content = inline.get('c', [])
                if len(content) >= 3:
                    target = content[2]
                    if isinstance(target, list) and len(target) >= 1:
                        url = target[0]
                        if isinstance(url, str) and url.startswith('#'):
                            anchor = url[1:]

                            target_type = None
                            if anchor.startswith('fig:') or anchor.startswith('fig_'):
                                target_type = 'fig'
                            elif anchor.startswith('tbl:') or anchor.startswith('tbl_'):
                                target_type = 'tbl'
                            elif anchor.startswith('eq:') or anchor.startswith('eq_'):
                                target_type = 'eq'

                            if target_type:
                                normalized_id = anchor.replace('_', ':') if ':' not in anchor else anchor

                                crossref = CrossReferenceUsage(
                                    target_id=normalized_id,
                                    target_type=target_type,
                                    context=context,
                                    source_file=source_file
                                )
                                section.cross_references.append(crossref)
                                structure.cross_references.append(crossref)

            # Recurse into nested inlines
            if 'c' in inline:
                content = inline['c']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, list):
                            self._find_citations(item, section, structure, context, source_file)

    def _build_hierarchy(self, structure: DocumentStructure):
        """Build parent-child relationships between sections."""
        section_stack: List[Section] = []

        for section in structure.sections:
            # Pop sections from stack that are not ancestors
            while section_stack and section_stack[-1].level >= section.level:
                section_stack.pop()

            # Set parent
            if section_stack:
                parent = section_stack[-1]
                section.parent = parent
                parent.children.append(section)
            else:
                # This is a root section
                structure.root_sections.append(section)

            # Push current section to stack
            section_stack.append(section)

    def _link_siblings(self, structure: DocumentStructure):
        """Link previous and next siblings at each level."""
        # Group sections by parent and level
        for parent_section in [None] + structure.sections:
            children = []
            if parent_section is None:
                children = structure.root_sections
            else:
                children = parent_section.children

            # Link siblings
            for i, section in enumerate(children):
                if i > 0:
                    section.previous_sibling = children[i - 1]
                if i < len(children) - 1:
                    section.next_sibling = children[i + 1]

    def _extract_id_from_attrs(self, attrs: Any) -> str:
        """Extract ID from Pandoc Attr structure."""
        if isinstance(attrs, dict):
            return attrs.get('id', '')
        elif isinstance(attrs, list) and len(attrs) >= 1:
            return attrs[0] if isinstance(attrs[0], str) else ''
        return ''

    def _extract_text_from_blocks(self, blocks: List[Any]) -> str:
        """Extract plain text from a list of block elements."""
        text_parts = []
        for block in blocks:
            if isinstance(block, dict):
                if block.get('t') in ['Para', 'Plain']:
                    inlines = block.get('c', [])
                    text_parts.append(self._extract_text_from_inlines(inlines))
                elif block.get('t') == 'Str':
                    text_parts.append(block.get('c', ''))
        return ' '.join(text_parts).strip()

    def _extract_text_from_inlines(self, inlines: List[Any]) -> str:
        """Extract plain text from a list of inline elements."""
        text_parts = []
        for inline in inlines:
            if isinstance(inline, dict):
                inline_type = inline.get('t')
                if inline_type == 'Str':
                    text_parts.append(inline.get('c', ''))
                elif inline_type == 'Space':
                    text_parts.append(' ')
                elif inline_type in ['Emph', 'Strong', 'Strikeout', 'Superscript', 'Subscript', 'SmallCaps']:
                    nested = inline.get('c', [])
                    text_parts.append(self._extract_text_from_inlines(nested))
                elif inline_type == 'Span':
                    content = inline.get('c', [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
                elif inline_type == 'Link':
                    content = inline.get('c', [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
                elif inline_type == 'Cite':
                    content = inline.get('c', [])
                    if len(content) >= 2:
                        text_parts.append(self._extract_text_from_inlines(content[1]))
        return ''.join(text_parts).strip()

