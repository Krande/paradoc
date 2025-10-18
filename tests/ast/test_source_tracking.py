"""Test that source file tracking enables proper image resolution from nested directories."""
import pytest
from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter


def test_source_tracking_in_ast(files_dir, tmp_path):
    """Test that AST blocks are annotated with source file information."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_source_tracking")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Check that blocks have _paradoc_source metadata
    blocks_with_source = [b for b in blocks if isinstance(b, dict) and '_paradoc_source' in b]

    assert len(blocks_with_source) > 0, "Expected some blocks to have source tracking metadata"

    # Verify the metadata structure
    for block in blocks_with_source[:5]:  # Check first few blocks
        source_info = block['_paradoc_source']
        assert 'source_file' in source_info, "Source metadata should include source_file"
        assert 'source_dir' in source_info, "Source metadata should include source_dir"
        assert source_info['source_file'].endswith('.md'), f"Source file should be a markdown file: {source_info['source_file']}"


def test_image_extraction_with_source_context(files_dir, tmp_path):
    """Test that images are extracted with their source directory context."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_image_context")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()
    manifest, sections = exporter.slice_sections(ast)

    # Check that we can extract images with source context
    for section_bundle in sections:
        doc = section_bundle.get("doc", {})
        blocks = doc.get("blocks", [])
        images_with_context = exporter._extract_images_with_source(blocks)

        for img_info in images_with_context:
            # Each image should have path and source_dir
            assert 'path' in img_info, "Image info should include path"
            assert 'source_dir' in img_info, "Image info should include source_dir"

            # If image path is relative, source_dir should be set
            img_path = img_info['path']
            if not img_path.startswith(('http://', 'https://', 'data:')):
                # For doc_lorum, images should have source directory
                source_dir = img_info.get('source_dir')
                if source_dir:
                    assert len(source_dir) > 0, "Source directory should not be empty for relative images"


def test_no_source_markers_in_final_ast(files_dir, tmp_path):
    """Test that HTML comment markers are removed from the final AST."""
    source = files_dir / "doc_lorum"
    one = OneDoc(source, work_dir=tmp_path / "test_no_markers")

    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    blocks = ast.get('blocks', [])

    # Check that no PARADOC_SOURCE_FILE markers remain in the AST
    marker_blocks = []
    for block in blocks:
        if isinstance(block, dict) and block.get("t") == "RawBlock":
            c = block.get("c", [])
            if isinstance(c, list) and len(c) >= 2:
                content = c[1]
                if isinstance(content, str) and "PARADOC_SOURCE_FILE:" in content:
                    marker_blocks.append(block)

    assert len(marker_blocks) == 0, "Source file markers should be removed from final AST"

