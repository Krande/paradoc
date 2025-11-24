"""Test that interactive plots work end-to-end."""

import pandas as pd
import numpy as np
from pathlib import Path
from paradoc import OneDoc
from paradoc.db import dataframe_to_plot_data

# Create a test document with plots
test_dir = Path(__file__).parent / "temp" / "test_interactive_plots"
test_dir.mkdir(parents=True, exist_ok=True)

# Create OneDoc instance
one = OneDoc(test_dir)

# Create sample plot data
x = np.linspace(0, 2 * np.pi, 100)
df = pd.DataFrame({"x": x, "sin(x)": np.sin(x), "cos(x)": np.cos(x)})

# Add plot to database
plot_data = dataframe_to_plot_data(
    key="test_plot", df=df, plot_type="line", caption="Test Interactive Plot", width=800, height=400
)
one.db_manager.add_plot(plot_data)

# Create markdown file
main_dir = test_dir / "00-main"
main_dir.mkdir(parents=True, exist_ok=True)

markdown_content = """# Interactive Plot Test

This document contains an interactive plot that should render with Plotly in the frontend.

## Test Plot

{{__test_plot__}}

The plot above should be interactive when viewed in the frontend.
"""

md_file = main_dir / "test.md"
md_file.write_text(markdown_content)

print("=" * 60)
print("Test document created successfully!")
print(f"Document directory: {test_dir}")
print("\nSending to frontend with use_static_html=True...")
print("=" * 60)

# Send to frontend
ok = one.send_to_frontend(embed_images=True, use_static_html=True)

if ok:
    print("\n✓ Document sent to frontend successfully!")
    print("✓ Check your browser - the plot should be interactive!")
    print("\nHow to verify:")
    print("1. Hover over the plot - you should see interactive tooltips")
    print("2. Try zooming, panning, or using the Plotly toolbar")
    print("3. The plot should respond to mouse interactions")
else:
    print("\n✗ Failed to send document to frontend")
