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

