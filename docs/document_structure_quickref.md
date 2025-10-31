# Document Structure API - Quick Reference

## Getting Started

```python
from paradoc import OneDoc

one = OneDoc("path/to/document")
structure = one.get_document_structure()
```

## Core Objects

### DocumentStructure
```python
structure.sections              # List[Section] - All sections
structure.root_sections         # List[Section] - Top-level only
structure.figures              # Dict[str, FigureRef] - By full_id
structure.tables               # Dict[str, TableRef] - By full_id
structure.equations            # Dict[str, EquationRef] - By full_id
structure.cross_references     # List[CrossReferenceUsage]
structure.metadata             # Dict[str, Any]
```

### Section
```python
section.id                     # str - Unique identifier
section.title                  # str - Section title
section.level                  # int - Heading level (1-6)
section.number                 # str - "1.2.3" or "A.1.2"
section.paragraphs             # List[Paragraph]
section.figures                # List[FigureRef]
section.tables                 # List[TableRef]
section.equations              # List[EquationRef]
section.cross_references       # List[CrossReferenceUsage]
section.parent                 # Optional[Section]
section.children               # List[Section]
section.previous_sibling       # Optional[Section]
section.next_sibling           # Optional[Section]
section.source_file            # Optional[str]
section.is_appendix           # bool
```

## Common Operations

### Finding Sections
```python
# By number
section = structure.get_section_by_number("2.1.3")

# By ID
section = structure.get_section_by_id("methodology")

# By level
level_1 = structure.get_sections_by_level(1)

# Main vs Appendix
main = structure.get_main_sections()
appendix = structure.get_appendix_sections()
```

### Navigating Hierarchy
```python
# Get path from root
path = section.get_path()  # [root, ..., section]

# Get depth
depth = section.get_depth()  # 0 for root

# Get all descendants
descendants = section.get_all_descendants()

# Navigate relatives
parent = section.parent
children = section.children
prev = section.previous_sibling
next = section.next_sibling
```

### Accessing Content
```python
# Paragraphs
for para in section.paragraphs:
    print(para.text)

# Figures
for fig in section.figures:
    print(f"{fig.full_id}: {fig.caption}")

# Tables
for tbl in section.tables:
    print(f"{tbl.full_id}: {tbl.caption}")

# Equations
for eq in section.equations:
    print(f"{eq.full_id}: {eq.latex}")

# Cross-references
for ref in section.cross_references:
    print(f"→ {ref.target_id} ({ref.target_type})")
```

### Statistics
```python
stats = structure.validate()

# Available stats:
stats['total_sections']
stats['root_sections']
stats['total_figures']
stats['total_tables']
stats['total_equations']
stats['total_cross_references']
stats['sections_by_level']  # Dict[int, int]
stats['appendix_sections']
stats['main_sections']
```

## Quick Recipes

### Print Table of Contents
```python
def print_toc(section, indent=0):
    print("  " * indent + f"{section.number} {section.title}")
    for child in section.children:
        print_toc(child, indent + 1)

for root in structure.root_sections:
    print_toc(root)
```

### Find Section with Most Figures
```python
section = max(structure.sections, key=lambda s: len(s.figures))
print(f"{section.number}: {len(section.figures)} figures")
```

### List All Figures by Section
```python
for section in structure.sections:
    if section.figures:
        print(f"\n{section.number} {section.title}")
        for fig in section.figures:
            print(f"  • {fig.full_id}")
```

### Validate All Cross-References
```python
valid = 0
invalid = 0

for ref in structure.cross_references:
    if ref.target_id in structure.figures or \
       ref.target_id in structure.tables or \
       ref.target_id in structure.equations:
        valid += 1
    else:
        invalid += 1
        print(f"Invalid: {ref.target_id}")

print(f"Valid: {valid}, Invalid: {invalid}")
```

### Group Sections by Source File
```python
from collections import defaultdict

by_file = defaultdict(list)
for section in structure.sections:
    if section.source_file:
        by_file[section.source_file].append(section.number)

for file, numbers in by_file.items():
    print(f"{file}: {', '.join(numbers)}")
```

### Count Content Types per Section
```python
for section in structure.sections:
    counts = {
        'paragraphs': len(section.paragraphs),
        'figures': len(section.figures),
        'tables': len(section.tables),
        'equations': len(section.equations),
        'cross_refs': len(section.cross_references)
    }
    if any(counts.values()):
        print(f"{section.number}: {counts}")
```

## Data Model Reference

### Paragraph
```python
text: str
ast_block: Optional[Dict]
source_file: Optional[str]
```

### FigureRef / TableRef
```python
ref_id: str              # "historical_trends"
full_id: str             # "fig:historical_trends"
caption: Optional[str]
source_file: Optional[str]
```

### EquationRef
```python
ref_id: str
full_id: str
latex: Optional[str]     # LaTeX content
source_file: Optional[str]
```

### CrossReferenceUsage
```python
target_id: str           # Full ID being referenced
target_type: str         # 'fig', 'tbl', or 'eq'
context: Optional[str]   # Surrounding text
source_file: Optional[str]
```

## See Also

- Full documentation: `docs/document_structure.md`
- Working example: `examples/document_structure_demo.py`
- Tests: `tests/ast/test_document_structure.py`
- Implementation: `src/paradoc/io/ast/document_structure.py`

