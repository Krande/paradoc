"""Camera preset model + loader + JSON export."""

import json
import textwrap

import pytest

from paradoc.camera import (
    BUILTIN_PRESETS,
    CameraPreset,
    export_presets_json,
    load_camera_presets,
)


def test_builtins_present():
    expected = {"iso_1", "iso_2", "iso_3", "iso_4", "top", "bottom", "front", "back", "left", "right"}
    assert set(BUILTIN_PRESETS) == expected


def test_preset_is_frozen():
    p = BUILTIN_PRESETS["iso_3"]
    with pytest.raises(Exception):
        p.azimuth_deg = 0  # type: ignore[misc]


def test_load_no_toml(tmp_path):
    presets = load_camera_presets(tmp_path / "missing.toml")
    assert set(presets) == set(BUILTIN_PRESETS)


def test_load_with_custom_overrides(tmp_path):
    toml_path = tmp_path / "paradoc.toml"
    toml_path.write_text(
        textwrap.dedent(
            """
            [cameras.custom.detail_iso]
            azimuth_deg = 45
            elevation_deg = 20
            distance = 0.6
            """
        )
    )
    presets = load_camera_presets(toml_path)
    assert "detail_iso" in presets
    assert presets["detail_iso"].azimuth_deg == 45
    assert presets["detail_iso"].distance == 0.6


def test_custom_overrides_builtin(tmp_path):
    toml_path = tmp_path / "paradoc.toml"
    toml_path.write_text(
        textwrap.dedent(
            """
            [cameras.custom.iso_3]
            azimuth_deg = 1
            """
        )
    )
    presets = load_camera_presets(toml_path)
    assert presets["iso_3"].azimuth_deg == 1


def test_export_json_round_trip(tmp_path):
    dest = tmp_path / "assets" / "presets.json"
    export_presets_json(BUILTIN_PRESETS, dest)
    payload = json.loads(dest.read_text(encoding="utf-8"))

    assert "iso_3" in payload
    assert payload["iso_3"]["azimuth_deg"] == -135
    # `name` is the dict key, not part of the value
    assert "name" not in payload["iso_3"]


def test_invalid_name_rejected():
    with pytest.raises(Exception):
        CameraPreset(name="has-dash")
