# Lorem Ipsum Demo Document

This is a comprehensive demonstration document showcasing paradoc's capabilities with extensive lorem ipsum content, multiple figures, tables, and plots.

## Document Structure

```
doc_lorum/
├── metadata.yaml           # Document configuration
├── 00-main/               # Main document section
│   ├── main.md           # Main content with 7 sections
│   └── images/           # 7 figures (plot1-7.png)
└── 01-appendix/          # Appendix section
    ├── appendix.md       # Appendix content with 4 sections
    └── images/           # 8 figures (arch1, bench1, etc.)
```

## Content Overview

### Main Section (00-main/main.md)
- **Executive Summary**: Introduction with footnotes
- **Introduction**: Background with subsections
  - Historical Perspective (with figure)
  - Current State Analysis (with table)
- **Methodology**: Data collection and analysis
  - Sample Selection Criteria
  - Measurement Protocols (with table)
  - Statistical Methods (with figure)
  - Validation Approach (with table)
- **Results and Analysis**: Primary findings
  - Quantitative Analysis (with table and figures)
  - Qualitative Observations
  - Comparative Analysis (with table and figure)
  - Error Analysis (with figure)
- **Discussion**: Interpretation and implications
  - Theory Comparison (with figure)
  - Limitations
  - Implications (with table)
- **Conclusions**: Key findings and recommendations
- **References**: Academic citations

### Appendix Section (01-appendix/appendix.md)
- **Technical Specifications**: System details
  - Component Specifications (with table)
  - Performance Benchmarks (with figure)
- **Detailed Experimental Data**: Raw data tables
  - Time Series Analysis (with figure)
- **Supplementary Calculations**: Mathematical derivations
  - Computational Results (with figure)
  - Algorithm Performance (with table)
- **Additional Figures**: Visualization gallery
  - Correlation Matrix (heatmap)
  - Distribution Plots
  - 3D Surface Plot
  - Statistical Tests (with table)
- **Data Processing Protocols**: QC procedures (with figure and table)
- **Glossary**: Term definitions

## Features Demonstrated

### Document Features
- ✅ Table of Contents (`\\toc`)
- ✅ Appendix section (`\\appendix`)
- ✅ Multiple heading levels (H1-H3)
- ✅ Numbered sections
- ✅ Cross-references to figures and tables
- ✅ Footnotes

### Content Elements
- ✅ **15 Tables**: Various data presentations
  - Performance metrics
  - Measurement specifications
  - Validation results
  - Quantitative analysis
  - Comparative data
  - Implementation guidelines
  - Statistical tests
  - Component specs
  - Raw experimental data
  - Algorithm performance
  - Validation criteria
  
- ✅ **15 Figures**: Diverse visualizations
  - Line plots (trends, time series, convergence)
  - Bar charts (performance, benchmarks)
  - Scatter plots (experimental data)
  - Histograms (distributions)
  - Heatmaps (correlations)
  - 3D surface plots
  - Workflow diagrams
  - Architecture diagrams

- ✅ **Lorem Ipsum Text**: Extensive placeholder content throughout
- ✅ **Bullet Lists**: Multiple formatted lists
- ✅ **Mathematical Equations**: Inline and display equations
- ✅ **Citations**: Figure and table references using pandoc-crossref syntax

## Usage

### Build the Document

To export this document to various formats:

```bash
# Export to HTML
pixi run paradoc export files/doc_lorum html

# Export to DOCX
pixi run paradoc export files/doc_lorum docx

# Export to PDF (requires LaTeX)
pixi run paradoc export files/doc_lorum pdf
```

### View the Document

The document includes proper cross-referencing:
- Figures are referenced as `[@fig:figure-id]`
- Tables are referenced as `[@tbl:table-id]`
- All references are clickable in the output

## Image Generation

All figures were generated using plotly with the `create_plots.py` script. To regenerate images:

```bash
cd files/doc_lorum
pixi run python create_plots.py
```

Images are saved as PNG files at 150 DPI for optimal quality in exported documents.

## Notes

- This document serves as a comprehensive test case for paradoc features
- All lorem ipsum content is placeholder text for demonstration purposes
- The document structure follows paradoc conventions with numbered directories (00-, 01-)
- Images are stored in subdirectories within each section

# Doc Lorum Example - Database Integration

This example demonstrates how to use **DbManager** to manage all plots and tables in a Paradoc document.

## Overview

The `doc_lorum` example has been updated to use the DbManager for all plot and table data instead of embedding them directly in markdown files or storing them as static images.

### Key Benefits

- **Centralized Data Management**: All plots and tables are stored in a SQLite database (`data.db`)
- **Dynamic Content**: Tables and plots can be filtered, sorted, and annotated without changing source data
- **Reusability**: Same data can be referenced multiple times with different views
- **Version Control**: Separates data from content, making markdown files cleaner

## Project Structure

```
doc_lorum/
├── data.db                    # SQLite database with all plots and tables
├── populate_database.py       # Script to populate the database
├── test_document.py          # Script to compile and test the document
├── metadata.yaml
├── SUMMARY.md
├── 00-main/
│   └── main.md               # Main content with {{__key__}} references
└── 01-app/
    └── appendix.md           # Appendix with {{__key__}} references
```

## Database Contents

### Tables (10 total)
- `current_metrics` - Current performance metrics summary
- `measurement_specs` - Measurement specifications and protocols
- `validation_results` - Validation test results summary
- `quantitative_metrics` - Quantitative analysis metrics
- `comparison_data` - Comparative analysis data across scenarios
- `implementation_guide` - Implementation phase guidelines
- `component_specs` - Component specifications and characteristics
- `raw_data_set1` - Raw experimental data - Set 1
- `raw_data_set2` - Raw experimental data - Set 2
- `algorithm_performance` - Algorithm performance comparison

### Plots (15 total)
- `historical_trends` - Historical trends visualization
- `data_framework` - Data collection framework architecture
- `statistical_workflow` - Statistical analysis workflow
- `primary_results` - Primary experimental results and trends
- `comparative_analysis` - Comparative analysis across conditions
- `error_analysis` - Error distribution and uncertainty analysis
- `theory_comparison` - Comparison between theory and experiments
- `system_architecture` - Detailed system architecture diagram
- `performance_benchmarks` - Performance benchmark results
- `time_series` - Time series analysis of key parameters
- `computational_results` - Computational simulation results
- `correlation_matrix` - Correlation matrix heatmap
- `distributions` - Distribution plots for all parameters
- `surface_plot` - 3D surface plot of interaction effects
- `box_plots` - Statistical distributions by condition

## Usage

### 1. Populate the Database

Run the population script to create/update the database with all plots and tables:

```bash
pixi run -e prod python files/doc_lorum/populate_database.py
```

This creates `data.db` in the `doc_lorum` directory with all the plot and table data.

### 2. Reference Data in Markdown

Use the `{{__key__}}` syntax to reference plots and tables from the database:

```markdown
# Example with a plot
{{__historical_trends__}}

As shown in [@fig:historical_trends], the data shows...

# Example with a table
{{__current_metrics__}}

The metrics in [@tbl:current_metrics] indicate...
```

**Important Notes:**
- Cross-reference IDs are automatically generated from the database keys
- Use underscores in cross-references (e.g., `@fig:historical_trends`)
- Do not add explicit `{#fig:...}` or `{#tbl:...}` tags - they're added automatically

### 3. Using Annotations

You can modify how tables are displayed using annotations:

```markdown
# Hide the index column
{{__current_metrics__}}{tbl:index:no}

# Sort by a column (descending)
{{__current_metrics__}}{tbl:sortby:Value:desc}

# Filter rows (regex pattern)
{{__current_metrics__}}{tbl:filter:Excellent}

# Combine multiple annotations
{{__current_metrics__}}{tbl:index:no;sortby:Value:desc;filter:Excellent}
```

For plots, you can adjust dimensions:

```markdown
# Custom width and height
{{__historical_trends__}}{plt:width:1000;height:600}
```

### 4. Compile the Document

Test the document compilation:

```bash
pixi run -e prod python files/doc_lorum/test_document.py
```

This will:
1. Verify the database connection
2. Export to HTML format
3. Export to DOCX format (Note: DOCX export has a known issue currently)

## How It Works

1. **Database Storage**: The `populate_database.py` script creates plotly figures and pandas DataFrames, converts them to PlotData and TableData objects, and stores them in the SQLite database.

2. **Markdown Processing**: When compiling, Paradoc scans markdown files for `{{__key__}}` patterns and replaces them with:
   - For tables: Markdown table syntax with caption and cross-reference ID
   - For plots: PNG images rendered from plotly figures with caption and cross-reference ID

3. **Cross-References**: The system automatically generates unique IDs for each plot/table based on their database keys, allowing proper cross-referencing throughout the document.

## Example Code

### Creating a Table for the Database

```python
from paradoc.db import dataframe_to_table_data

df = pd.DataFrame({
    "Metric": ["Value1", "Value2"],
    "Score": [85, 92]
})

table_data = dataframe_to_table_data(
    key="my_table",
    df=df,
    caption="My Table Caption",
    show_index=False
)

one.db_manager.add_table(table_data)
```

### Creating a Plot for the Database

```python
from paradoc.db import plotly_figure_to_plot_data
import plotly.express as px

fig = px.line(df, x="x", y="y", title="My Plot")

plot_data = plotly_figure_to_plot_data(
    key="my_plot",
    fig=fig,
    caption="My plot caption",
    width=800,
    height=500
)

one.db_manager.add_plot(plot_data)
```

## Known Issues

- **DOCX Export**: Currently experiencing issues with table formatting in DOCX export. HTML export works perfectly.
- The static `images/` directories are no longer used - all plots are generated from database at compile time

## Summary

The doc_lorum example now demonstrates a complete database-driven workflow:
- ✅ 15 plots stored in database
- ✅ 10 tables stored in database
- ✅ Dynamic cross-referencing
- ✅ Table annotations (sort, filter, hide index)
- ✅ HTML export working perfectly
- ⚠️ DOCX export needs debugging
