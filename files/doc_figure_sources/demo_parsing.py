"""Demo script to test figure source parsing functionality."""

from pathlib import Path

from files.doc_figure_sources.source_handler import parse_figure_sources_from_file


def main():
    # Parse the markdown file
    markdown_path = Path(__file__).parent / "00-main/main.md"
    figure_sources = parse_figure_sources_from_file(markdown_path)

    print(f"Found {len(figure_sources)} figure source specifications:\n")

    for i, spec in enumerate(figure_sources, start=1):
        print(f"{i}. {spec.figure_source}: {spec.figure_title}")
        print(f"   Type: {type(spec).__name__}")
        print(f"   Camera: {spec.camera_pos}")

        if hasattr(spec, 'fea_format'):
            print(f"   FEA Format: {spec.fea_format}")
        if hasattr(spec, 'output_file'):
            print(f"   Output File: {spec.output_file}")
        if hasattr(spec, 'field'):
            print(f"   Field: {spec.field}")

        print(f"   Source Input: {spec.source_inp}")
        print()

if __name__ == '__main__':
    main()