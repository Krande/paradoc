"""Handler for parsing and processing figure source specifications from markdown.

This module provides functionality to:
1. Parse figure source specifications from markdown files using <-- --> markers
2. Validate them against pydantic models
3. Generate figures based on the specifications
"""

import re
from pathlib import Path
from typing import List, Tuple

from .source_models import (
    FigureSourceSpec,
    CADModelFile,
    FEAModel,
    FEAModelResults,
    create_figure_source,
)


def extract_figure_sources(markdown_content: str) -> List[Tuple[int, int, str]]:
    """Extract all figure source specifications from markdown content.

    Args:
        markdown_content: The markdown content as a string

    Returns:
        List of tuples containing (start_pos, end_pos, spec_content)
    """
    pattern = r'<--\s*\n(.*?)\n-->'
    matches = re.finditer(pattern, markdown_content, re.DOTALL)

    results = []
    for match in matches:
        start_pos = match.start()
        end_pos = match.end()
        spec_content = match.group(1).strip()
        results.append((start_pos, end_pos, spec_content))

    return results


def parse_spec_content(spec_content: str) -> dict:
    """Parse the content of a figure source specification into a dictionary.

    Args:
        spec_content: The content between <-- and --> markers

    Returns:
        Dictionary with parsed key-value pairs
    """
    data = {}

    # Split by lines and parse key: value pairs
    for line in spec_content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Split on first colon only
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            data[key] = value

    return data


def parse_figure_sources_from_markdown(markdown_content: str) -> List[FigureSourceSpec]:
    """Parse all figure source specifications from markdown content.

    Args:
        markdown_content: The markdown content as a string

    Returns:
        List of validated FigureSourceSpec instances

    Raises:
        ValueError: If a specification fails validation
    """
    extracted = extract_figure_sources(markdown_content)
    figure_sources = []

    for start_pos, end_pos, spec_content in extracted:
        try:
            data = parse_spec_content(spec_content)
            figure_source = create_figure_source(data)
            figure_sources.append(figure_source)
        except Exception as e:
            raise ValueError(
                f"Failed to parse figure source at position {start_pos}-{end_pos}: {e}"
            ) from e

    return figure_sources


def parse_figure_sources_from_file(markdown_path: Path) -> List[FigureSourceSpec]:
    """Parse all figure source specifications from a markdown file.

    Args:
        markdown_path: Path to the markdown file

    Returns:
        List of validated FigureSourceSpec instances
    """
    content = markdown_path.read_text(encoding='utf-8')
    return parse_figure_sources_from_markdown(content)


# Template generator functions - to be implemented

def generate_cad_model_figure(spec: CADModelFile, output_path: Path) -> None:
    """Generate a rasterized PNG figure from a CAD model specification.

    Args:
        spec: The validated CAD model specification
        output_path: Path where the PNG figure should be saved

    TODO: Implement CAD model rendering logic
    """
    raise NotImplementedError(
        f"CAD model rendering not yet implemented. "
        f"Would render {spec.source_inp} to {output_path} with camera {spec.camera_pos}"
    )


def generate_fea_model_figure(spec: FEAModel, output_path: Path) -> None:
    """Generate a rasterized PNG figure from an FEA model specification.

    Args:
        spec: The validated FEA model specification
        output_path: Path where the PNG figure should be saved

    TODO: Implement FEA model geometry rendering logic
    """
    raise NotImplementedError(
        f"FEA model rendering not yet implemented. "
        f"Would render {spec.source_inp} ({spec.fea_format}) to {output_path} "
        f"with camera {spec.camera_pos}"
    )


def generate_fea_results_figure(spec: FEAModelResults, output_path: Path) -> None:
    """Generate a rasterized PNG figure from FEA results specification.

    Args:
        spec: The validated FEA results specification
        output_path: Path where the PNG figure should be saved

    TODO: Implement FEA results visualization logic
    """
    raise NotImplementedError(
        f"FEA results rendering not yet implemented. "
        f"Would render {spec.output_file} ({spec.fea_format}) field '{spec.field}' "
        f"to {output_path} with camera {spec.camera_pos}"
    )


def generate_figure(spec: FigureSourceSpec, output_path: Path) -> None:
    """Generate a rasterized PNG figure based on the specification type.

    This is the main dispatcher function that routes to the appropriate
    generator based on the figure source type.

    Args:
        spec: The validated figure source specification
        output_path: Path where the PNG figure should be saved

    Raises:
        NotImplementedError: If the generator is not yet implemented
        ValueError: If the specification type is not recognized
    """
    if isinstance(spec, CADModelFile):
        generate_cad_model_figure(spec, output_path)
    elif isinstance(spec, FEAModel):
        generate_fea_model_figure(spec, output_path)
    elif isinstance(spec, FEAModelResults):
        generate_fea_results_figure(spec, output_path)
    else:
        raise ValueError(f"Unknown figure source type: {type(spec)}")


def process_markdown_file(
    markdown_path: Path,
    output_dir: Path,
    filename_template: str = "{index:03d}_{title}.png"
) -> List[Tuple[FigureSourceSpec, Path]]:
    """Process a markdown file and generate all specified figures.

    Args:
        markdown_path: Path to the markdown file
        output_dir: Directory where generated figures should be saved
        filename_template: Template for output filenames. Can use {index} and {title}

    Returns:
        List of tuples containing (spec, output_path) for each generated figure

    Raises:
        NotImplementedError: If any generator is not yet implemented
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    figure_sources = parse_figure_sources_from_file(markdown_path)
    results = []

    for index, spec in enumerate(figure_sources, start=1):
        # Create filename from template
        title_slug = spec.figure_title.lower().replace(' ', '_')
        filename = filename_template.format(index=index, title=title_slug)
        output_path = output_dir / filename

        # Generate the figure
        generate_figure(spec, output_path)
        results.append((spec, output_path))

    return results

