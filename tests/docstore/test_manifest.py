"""Bundle manifest read/write."""

from paradoc.docstore import BUNDLE_VERSION, read_manifest, write_manifest


def test_round_trip(tmp_path):
    write_manifest(tmp_path, doc_id="proj_alpha")
    m = read_manifest(tmp_path)
    assert m.doc_id == "proj_alpha"
    assert m.bundle_version == BUNDLE_VERSION
    assert m.created_at  # truthy ISO string


def test_missing_manifest_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        read_manifest(tmp_path)
