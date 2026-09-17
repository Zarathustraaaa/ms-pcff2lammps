import json
from pathlib import Path


def test_shipped_validation_record_is_pass_and_precise():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "validation" / "paam-pentamer-20260917.json").read_text())
    assert data["status"] == "PCFF_LAMMPS_PARITY_FINAL_PASS"
    assert data["required_missing"] == 0
    assert data["unexpected_missing_bendbend"] == 0
    assert data["relative_total_energy_rmse_kcal_mol"] < 1.0e-6
    assert data["relative_total_energy_max_abs_kcal_mol"] < 1.0e-6
