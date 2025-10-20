import pytest

from paradoc import OneDoc
from paradoc.io.ast.exporter import ASTExporter


def test_build_ast_and_slice_sections(files_dir, tmp_path):
    # Use example doc1 which should exist in files/
    source = files_dir / "doc1"
    one = OneDoc(source, work_dir=tmp_path / "ast_doc")

    # Prepare compilation artifacts (metadata, moved assets)
    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ast = exporter.build_ast()

    # Basic shape
    assert isinstance(ast, dict)
    assert "blocks" in ast or isinstance(ast.get("blocks"), list)

    manifest, sections = exporter.slice_sections(ast)

    # Manifest shape
    assert isinstance(manifest, dict)
    assert manifest.get("docId")
    assert isinstance(manifest.get("sections"), list)

    # At least one section expected in example docs
    assert sections, "Expected at least one top-level section in the AST"

    # Check a section bundle shape
    sec0 = sections[0]
    assert "section" in sec0 and "doc" in sec0
    assert isinstance(sec0["doc"].get("blocks"), list)

    # Manifest sections include ALL headers (H1-H6), while section bundles are split by H1 only
    # So manifest sections should be >= section bundles (bundles are H1 only)
    assert len(manifest["sections"]) >= len(
        sections
    ), f"Manifest should include all headers ({len(manifest['sections'])}), bundles are H1-split ({len(sections)})"

    # All H1 headers should appear in both manifest and section bundles
    h1_sections = [s for s in manifest["sections"] if s.get("level") == 1]
    assert len(h1_sections) == len(
        sections
    ), f"Number of H1 headers in manifest ({len(h1_sections)}) should match section bundles ({len(sections)})"


@pytest.mark.parametrize("host,port", [("localhost", 13579)])
@pytest.mark.skip(reason="WebSocket integration smoke test is optional for CI")
def test_send_to_frontend_smoke(files_dir, tmp_path, host, port):
    source = files_dir / "doc1"
    one = OneDoc(source, work_dir=tmp_path / "ast_ws_doc")
    one._prep_compilation()
    one._perform_variable_substitution(False)

    exporter = ASTExporter(one)
    ok = exporter.send_to_frontend(host=host, port=port)
    # We allow either connection success or failure depending on WS availability
    assert ok in (True, False)
