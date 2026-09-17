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
