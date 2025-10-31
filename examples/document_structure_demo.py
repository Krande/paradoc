"""Example script demonstrating the DocumentStructure extraction feature.

This example shows how to use the new get_document_structure() method to:
1. Extract the complete section hierarchy
2. Navigate through sections
3. Find content within sections
4. Validate cross-references
"""

from pathlib import Path
from paradoc import OneDoc


def main():
    # Initialize OneDoc with a document
    source_dir = Path(__file__).parent.parent / "files" / "doc_lorum"
    one = OneDoc(source_dir)
    
    print("=" * 80)
    print("Document Structure Extraction Example")
    print("=" * 80)
    
    # Extract document structure
    print("\n[1] Extracting document structure...")
    structure = one.get_document_structure()
    
    # Validate and get statistics
    stats = structure.validate()
    print(f"\n[2] Document Statistics:")
    print(f"  • Total sections: {stats['total_sections']}")
    print(f"  • Root sections: {stats['root_sections']}")
    print(f"  • Figures: {stats['total_figures']}")
    print(f"  • Tables: {stats['total_tables']}")
    print(f"  • Equations: {stats['total_equations']}")
    print(f"  • Cross-references: {stats['total_cross_references']}")
    print(f"  • Main sections: {stats['main_sections']}")
    print(f"  • Appendix sections: {stats['appendix_sections']}")
    
    # Display section hierarchy
    print(f"\n[3] Section Hierarchy:")
    for root in structure.root_sections:
        print_section_tree(root, indent=0)
    
    # Find a specific section and show its content
    print(f"\n[4] Example Section Content:")
    intro_section = structure.get_section_by_number("2")
    if intro_section:
        print(f"  Section {intro_section.number}: {intro_section.title}")
        print(f"  • Paragraphs: {len(intro_section.paragraphs)}")
        print(f"  • Figures: {len(intro_section.figures)}")
        print(f"  • Tables: {len(intro_section.tables)}")
        print(f"  • Equations: {len(intro_section.equations)}")
        print(f"  • Cross-references: {len(intro_section.cross_references)}")
        
        if intro_section.figures:
            print(f"\n  Figures in this section:")
            for fig in intro_section.figures:
                print(f"    - {fig.full_id}: {fig.caption[:60] if fig.caption else 'No caption'}...")
        
        if intro_section.cross_references:
            print(f"\n  Cross-references in this section:")
            for crossref in intro_section.cross_references[:3]:  # Show first 3
                print(f"    - References {crossref.target_id} ({crossref.target_type})")
    
    # Navigate section hierarchy
    print(f"\n[5] Section Navigation Example:")
    if len(structure.sections) > 5:
        section = structure.sections[5]
        print(f"  Current section: {section.number} - {section.title}")
        
        path = section.get_path()
        print(f"  Path from root: {' → '.join([f'{s.number}' for s in path])}")
        print(f"  Depth: {section.get_depth()}")
        
        if section.parent:
            print(f"  Parent: {section.parent.number} - {section.parent.title}")
        
        if section.children:
            print(f"  Children: {', '.join([f'{c.number}' for c in section.children])}")
        
        if section.previous_sibling:
            print(f"  Previous sibling: {section.previous_sibling.number}")
        
        if section.next_sibling:
            print(f"  Next sibling: {section.next_sibling.number}")
    
    # Show appendix sections
    print(f"\n[6] Appendix Sections:")
    appendix_sections = structure.get_appendix_sections()
    for section in appendix_sections[:5]:  # Show first 5
        print(f"  {section.number}: {section.title}")
    
    # Validate cross-references
    print(f"\n[7] Cross-Reference Validation:")
    dangling_count = 0
    for crossref in structure.cross_references:
        if crossref.target_id not in structure.figures and \
           crossref.target_id not in structure.tables and \
           crossref.target_id not in structure.equations:
            dangling_count += 1
    
    if dangling_count == 0:
        print(f"  ✓ All {len(structure.cross_references)} cross-references are valid!")
    else:
        print(f"  ✗ Found {dangling_count} dangling cross-references")
    
    print("\n" + "=" * 80)
    print("Complete!")
    print("=" * 80)


def print_section_tree(section, indent=0):
    """Recursively print section tree with indentation."""
    prefix = "  " * indent
    print(f"{prefix}{section.number}: {section.title}")
    
    for child in section.children:
        print_section_tree(child, indent + 1)


if __name__ == "__main__":
    main()

