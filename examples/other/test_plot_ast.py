"""Test script to verify data-plot-key attributes are added to AST."""

from pathlib import Path
from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter

# Use the plot demo document
demo_dir = Path(__file__).parent / "temp" / "plot_demo"

if not demo_dir.exists():
    print("Plot demo not found. Run plot_demo.py first.")
    exit(1)

# Create OneDoc instance
one = OneDoc(demo_dir)

# Perform variable substitution
one._prep_compilation()
one._perform_variable_substitution(False)

# Build AST
exporter = ASTExporter(one)
ast = exporter.build_ast()


# Search for Figure blocks with data-plot-key
def find_figures(blocks, depth=0):
    """Recursively find Figure blocks."""
    figures = []
    for block in blocks:
        if not isinstance(block, dict):
            continue

        if block.get("t") == "Figure":
            figures.append(block)
            # Print figure details
            c = block.get("c", [])
            if len(c) >= 1:
                attr = c[0]
                if isinstance(attr, list) and len(attr) >= 3:
                    fig_id = attr[0]
                    attrs = attr[2]
                    print(f"{'  ' * depth}Figure: {fig_id}")
                    print(f"{'  ' * depth}  Attributes: {attrs}")
                    # Check for data-plot-key
                    has_plot_key = any(a[0] == "data-plot-key" for a in attrs if isinstance(a, list) and len(a) >= 2)
                    if has_plot_key:
                        plot_key = next(
                            a[1] for a in attrs if isinstance(a, list) and len(a) >= 2 and a[0] == "data-plot-key"
                        )
                        print(f"{'  ' * depth}  ✓ Has data-plot-key: {plot_key}")
                    else:
                        print(f"{'  ' * depth}  ✗ Missing data-plot-key")

        # Recurse into nested blocks
        if block.get("t") in ["Div", "BlockQuote"]:
            c = block.get("c", [])
            if isinstance(c, list) and len(c) >= 2:
                nested_blocks = c[1]
                if isinstance(nested_blocks, list):
                    figures.extend(find_figures(nested_blocks, depth + 1))

    return figures


print("=" * 60)
print("Searching for Figure blocks in AST...")
print("=" * 60)

blocks = ast.get("blocks", [])
figures = find_figures(blocks)

print("\n" + "=" * 60)
print(f"Found {len(figures)} figure(s) total")
print("=" * 60)

# Check plot keys in database
plot_keys = one.db_manager.list_plots()
print(f"\nPlots in database: {plot_keys}")
