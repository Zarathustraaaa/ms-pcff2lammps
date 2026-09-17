import pytest

from ms_pcff2lammps.converter import bonded_parity_rows, parse_lammps_thermo


def test_parse_fixed_coordinate_thermo():
    log = """
Step PotEng E_bond E_angle E_dihed E_impro TotEng
0 -10.0 1.0 2.0 3.0 4.0 -10.0
"""
    values = parse_lammps_thermo(log)
    assert values == {"ebond": 1.0, "eangle": 2.0, "edihed": 3.0, "eimp": 4.0}


def test_bonded_parity_uses_supplied_reference_only():
    values = {"ebond": 1.0, "eangle": 2.0, "edihed": 3.0, "eimp": 4.0}
    targets = {"ebond": 1.0, "eangle": 2.0, "edihed": 3.0, "eimp": 4.0005}
    rows = bonded_parity_rows(values, targets, 1.0e-3)
    assert all(row["pass"] for row in rows)
    eimp = next(row for row in rows if row["field"] == "eimp")
    assert eimp["delta"] == pytest.approx(-5.0e-4)
