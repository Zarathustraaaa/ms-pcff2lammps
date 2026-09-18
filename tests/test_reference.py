import json

import pytest

from ms_pcff2lammps.converter import resolve_bonded_reference


def test_no_reference_is_selected_implicitly():
    assert resolve_bonded_reference() is None


def test_reference_json(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text(
        json.dumps(
            {
                "label": "synthetic",
                "tolerance_kcal_mol": 0.01,
                "ebond": 1.0,
                "eangle": 2.0,
                "edihed": 3.0,
                "eimp": 4.0,
            }
        )
    )
    targets, tolerance, label = resolve_bonded_reference(json_path=path)
    assert targets["eimp"] == 4.0
    assert tolerance == 0.01
    assert label == "synthetic"


def test_reference_json_rejects_missing_fields(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text('{"ebond": 1}')
    with pytest.raises(ValueError):
        resolve_bonded_reference(json_path=path)


def test_reference_json_rejects_nonfinite_values(tmp_path):
    path = tmp_path / "reference.json"
    path.write_text(
        json.dumps(
            {
                "label": "nonfinite",
                "tolerance_kcal_mol": 0.001,
                "ebond": 1.0,
                "eangle": 2.0,
                "edihed": float("nan"),
                "eimp": 4.0,
            }
        )
    )
    with pytest.raises(ValueError, match="must be finite"):
        resolve_bonded_reference(json_path=path)


def test_reference_json_must_exist(tmp_path):
    with pytest.raises(ValueError, match="reference JSON not found"):
        resolve_bonded_reference(json_path=tmp_path / "missing.json")
