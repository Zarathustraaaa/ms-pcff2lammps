import pytest

from ms_pcff2lammps.converter import main


def test_native_bendbend_requires_named_profile(tmp_path, capsys):
    rc = main(
        [
            "generate",
            "--car", str(tmp_path / "a.car"),
            "--mdf", str(tmp_path / "a.mdf"),
            "--off", str(tmp_path / "pcff.off"),
            "--native-bendbend", str(tmp_path / "bendbend.csv"),
        ]
    )
    assert rc == 2
    assert "requires an explicit validated --bendbend-profile" in capsys.readouterr().err


def test_generate_cross_zero_requires_source_assertion(tmp_path, capsys):
    rc = main(
        [
            "generate",
            "--car", str(tmp_path / "a.car"),
            "--mdf", str(tmp_path / "a.mdf"),
            "--off", str(tmp_path / "pcff.off"),
            "--native-bendbend", str(tmp_path / "bendbend.csv"),
            "--bendbend-profile", "paam-pentamer-20260917",
            "--reference-json", str(tmp_path / "reference.json"),
            "--allow-forcite-cross-zero",
        ]
    )
    assert rc == 2
    assert "requires --forcite-missing-parameters 0" in capsys.readouterr().err


def test_generate_cross_zero_requires_matching_reference(tmp_path, capsys):
    rc = main(
        [
            "generate",
            "--car", str(tmp_path / "a.car"),
            "--mdf", str(tmp_path / "a.mdf"),
            "--off", str(tmp_path / "pcff.off"),
            "--native-bendbend", str(tmp_path / "bendbend.csv"),
            "--bendbend-profile", "paam-pentamer-20260917",
            "--forcite-missing-parameters", "0",
            "--allow-forcite-cross-zero",
        ]
    )
    assert rc == 2
    assert "requires --reference-json" in capsys.readouterr().err


def test_audit_does_not_expose_cross_zero_override(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["audit", "--help"])
    assert exc.value.code == 0
    assert "--allow-forcite-cross-zero" not in capsys.readouterr().out
