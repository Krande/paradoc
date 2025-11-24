# Document Structure Extraction

The `DocumentStructureExtractor` provides a comprehensive way to extract and navigate the hierarchical structure of your documents. This feature extracts not just sections, but also their content, relationships, and cross-references.

## Overview

The document structure extraction system provides:

- **Section Hierarchy**: Complete tree structure with parent-child relationships
- **Section Navigation**: Navigate between siblings, parents, and children
- **Content Tracking**: Paragraphs, figures, tables, and equations within each section
- **Cross-References**: Track all cross-reference usages within sections
- **Source Tracking**: Track which source markdown file each element came from
- **Section Numbering**: Automatic numbering (1.2.3 for main, A.1.2 for appendix)

## Quick Start

```python
from paradoc import OneDoc

# Initialize your document
one = OneDoc("path/to/your/document")

# Extract the complete document structure
structure = one.get_document_structure()

# Get statistics
stats = structure.validate()
print(f"Document has {stats['total_sections']} sections")
print(f"  - {stats['total_figures']} figures")
print(f"  - {stats['total_tables']} tables")
print(f"  - {stats['total_equations']} equations")

# Navigate the hierarchy
for root_section in structure.root_sections:
    print(f"{root_section.number}: {root_section.title}")
    for child in root_section.children:
        print(f"  {child.number}: {child.title}")
```

## Data Models

### Section

The main container for document sections:

```python
class Section(BaseModel):
    id: str                              # Unique identifier
    title: str                           # Section title
    level: int                           # Heading level (1-6)
    number: str                          # Numeric index (e.g., "1.2.3", "A.1")
    
    # Content
    paragraphs: List[Paragraph]          # Paragraphs in this section
    figures: List[FigureRef]             # Figures defined in this section
    tables: List[TableRef]               # Tables defined in this section
    equations: List[EquationRef]         # Equations defined in this section
    cross_references: List[CrossReferenceUsage]  # Cross-refs used here
    
    # Hierarchy Navigation
    parent: Optional[Section]            # Parent section
    children: List[Section]              # Child sections
    previous_sibling: Optional[Section]  # Previous section at same level
    next_sibling: Optional[Section]      # Next section at same level
    
    # Metadata
    source_file: Optional[str]           # Source markdown file
    is_appendix: bool                    # Whether in appendix
    ast_block: Optional[Dict]            # Original AST block
```

### FigureRef, TableRef, EquationRef

References to document elements:

```python
class FigureRef(BaseModel):
    ref_id: str                # Semantic ID (e.g., "historical_trends")
    full_id: str               # Full ID with prefix (e.g., "fig:historical_trends")
    caption: Optional[str]     # Caption text
    source_file: Optional[str] # Source markdown file

class TableRef(BaseModel):
    ref_id: str
    full_id: str
    caption: Optional[str]
    source_file: Optional[str]

class EquationRef(BaseModel):
    ref_id: str
    full_id: str
    latex: Optional[str]       # LaTeX content
    source_file: Optional[str]
```

### CrossReferenceUsage

Tracks where cross-references are used:

```python
class CrossReferenceUsage(BaseModel):
    target_id: str             # Full ID being referenced
    target_type: str           # Type: 'fig', 'tbl', or 'eq'
    context: Optional[str]     # Surrounding text
    source_file: Optional[str] # Source markdown file
```

### DocumentStructure

The top-level container:

```python
class DocumentStructure(BaseModel):
    sections: List[Section]                  # All sections in order
    root_sections: List[Section]             # Top-level sections
    figures: Dict[str, FigureRef]            # All figures by full_id
    tables: Dict[str, TableRef]              # All tables by full_id
    equations: Dict[str, EquationRef]        # All equations by full_id
    cross_references: List[CrossReferenceUsage]  # All cross-references
    metadata: Dict[str, Any]                 # Document metadata
```

## Common Use Cases

### 1. Navigating the Section Hierarchy

```python
structure = one.get_document_structure()

# Iterate through all sections
for section in structure.sections:
    print(f"{section.number}: {section.title}")

# Get only top-level sections
for root in structure.root_sections:
    print(f"Root section: {root.title}")

# Navigate from a section to its parent
section = structure.sections[5]
if section.parent:
    print(f"Parent: {section.parent.title}")

# Get all children of a section
for child in section.children:
    print(f"Child: {child.number} - {child.title}")

# Navigate to siblings
if section.next_sibling:
    print(f"Next: {section.next_sibling.title}")
if section.previous_sibling:
    print(f"Previous: {section.previous_sibling.title}")
```

### 2. Finding Sections by Various Criteria

```python
# Find by section number
section = structure.get_section_by_number("2.1.3")

# Find by section ID
section = structure.get_section_by_id("methodology")

# Get all sections at a specific level
level_1_sections = structure.get_sections_by_level(1)

# Get main vs appendix sections
main_sections = structure.get_main_sections()
appendix_sections = structure.get_appendix_sections()
```

### 3. Accessing Section Content

```python
section = structure.get_section_by_number("3")

# Get paragraphs
for para in section.paragraphs:
    print(para.text[:100])  # First 100 chars

# Get figures in this section
for fig in section.figures:
    print(f"Figure: {fig.full_id} - {fig.caption}")

# Get tables in this section
for tbl in section.tables:
    print(f"Table: {tbl.full_id} - {tbl.caption}")

# Get equations in this section
for eq in section.equations:
    print(f"Equation: {eq.full_id} - {eq.latex}")

# Get cross-references used in this section
for crossref in section.cross_references:
    print(f"References {crossref.target_id} ({crossref.target_type})")
```

### 4. Working with Section Paths and Depth

```python
section = structure.get_section_by_number("3.2.1")

# Get path from root to this section
path = section.get_path()
for s in path:
    print(f"{s.number}: {s.title}")

# Get depth (0 for root sections)
depth = section.get_depth()
print(f"Section is at depth {depth}")

# Get all descendants recursively
descendants = section.get_all_descendants()
print(f"Section has {len(descendants)} descendants")
```

### 5. Validating Cross-References

```python
structure = one.get_document_structure()

# Check for dangling references
for crossref in structure.cross_references:
    target_id = crossref.target_id
    
    if target_id not in structure.figures and \
       target_id not in structure.tables and \
       target_id not in structure.equations:
        print(f"WARNING: Dangling reference to {target_id}")

# Get statistics
stats = structure.validate()
print(f"Total cross-references: {stats['total_cross_references']}")
```

### 6. Generating Table of Contents

```python
def generate_toc(structure):
    """Generate a hierarchical table of contents."""
    lines = []
    
    for root in structure.root_sections:
        _add_section_to_toc(root, lines, indent=0)
    
    return "\n".join(lines)

def _add_section_to_toc(section, lines, indent):
    prefix = "  " * indent
    lines.append(f"{prefix}{section.number} {section.title}")
    
    for child in section.children:
        _add_section_to_toc(child, lines, indent + 1)

toc = generate_toc(structure)
print(toc)
```

### 7. Finding Which Section Contains an Element

```python
# Find which section contains a specific figure
figure_id = "fig:results_plot"

for section in structure.sections:
    for fig in section.figures:
        if fig.full_id == figure_id:
            print(f"Figure {figure_id} is in section {section.number}: {section.title}")
            break

# Or look up the figure and then find its section
if figure_id in structure.figures:
    figure = structure.figures[figure_id]
    # Find the section by checking which section contains this figure
    for section in structure.sections:
        if any(f.full_id == figure_id for f in section.figures):
            print(f"Found in section: {section.number}")
```

### 8. Analyzing Section Statistics

```python
structure = one.get_document_structure()

# Count content per section
for section in structure.sections:
    content_count = (
        len(section.paragraphs) +
        len(section.figures) +
        len(section.tables) +
        len(section.equations)
    )
    print(f"{section.number} {section.title}: {content_count} items")

# Find sections with most figures
sections_by_figures = sorted(
    structure.sections,
    key=lambda s: len(s.figures),
    reverse=True
)
print(f"Section with most figures: {sections_by_figures[0].number}")
```

### 9. Source File Tracking

```python
# Find which source file each section came from
for section in structure.sections:
    if section.source_file:
        print(f"{section.number}: {section.source_file}")

# Group sections by source file
from collections import defaultdict
sections_by_file = defaultdict(list)

for section in structure.sections:
    if section.source_file:
        sections_by_file[section.source_file].append(section)

for source_file, sections in sections_by_file.items():
    print(f"\n{source_file}:")
    for section in sections:
        print(f"  {section.number}: {section.title}")
```

## Section Numbering

The extractor automatically generates section numbers following the OneDoc convention:

### Main Sections
- Level 1: `1`, `2`, `3`, ...
- Level 2: `1.1`, `1.2`, `2.1`, ...
- Level 3: `1.1.1`, `1.2.1`, `2.1.1`, ...

### Appendix Sections
- Level 1: `A`, `B`, `C`, ...
- Level 2: `A.1`, `A.2`, `B.1`, ...
- Level 3: `A.1.1`, `A.2.1`, `B.1.1`, ...

## Performance Considerations

The document structure is built once from the AST and includes all relationships pre-computed. This means:

- **Initial extraction**: Takes time to parse AST (similar to CrossRefExtractor)
- **Navigation**: Instant - all relationships are pre-computed
- **Lookups**: Fast - uses dictionaries for O(1) lookup by ID
- **Memory**: Stores complete structure in memory

For very large documents (1000+ sections), consider processing in chunks or using lazy loading patterns.

## Integration with CrossRefExtractor

While `DocumentStructureExtractor` extracts the complete document structure including cross-references, the standalone `CrossRefExtractor` is still useful for:

- Validating cross-references without building full hierarchy
- Lightweight cross-reference checking in CI/CD pipelines
- Extracting just cross-reference data without section information

Both extractors work on the same AST and produce compatible data.

## Example: Complete Document Analysis

See `examples/document_structure_demo.py` for a complete working example that demonstrates:

- Extracting the structure
- Getting statistics
- Navigating the hierarchy
- Finding content within sections
- Validating cross-references
- Working with section paths

## API Reference

### OneDoc.get_document_structure()

```python
def get_document_structure(self, metadata_file=None) -> DocumentStructure:
    """Get the complete document structure with section hierarchy.
    
    Args:
        metadata_file: Optional metadata file path
        
    Returns:
        DocumentStructure object containing the complete document hierarchy
    """
```

### DocumentStructure Methods

- `get_section_by_id(section_id: str) -> Optional[Section]`
- `get_section_by_number(number: str) -> Optional[Section]`
- `get_sections_by_level(level: int) -> List[Section]`
- `get_appendix_sections() -> List[Section]`
- `get_main_sections() -> List[Section]`
- `validate() -> Dict[str, Any]` - Returns validation statistics

### Section Methods

- `get_all_descendants() -> List[Section]` - Get all descendant sections recursively
- `get_path() -> List[Section]` - Get path from root to this section
- `get_depth() -> int` - Get depth of this section (root is 0)

## Testing

The document structure extraction is thoroughly tested in `tests/ast/test_document_structure.py` with tests covering:

- Basic structure extraction
- Section hierarchy and navigation
- Section content (paragraphs, figures, tables, equations)
- Navigation methods (path, depth, descendants)
- Cross-reference tracking within sections
- Lookup methods
- Source file tracking
- Specific figure/table/equation detection

Run tests with:
```bash
pixi run test tests/ast/test_document_structure.py
```

