from ms_pcff2lammps.converter import write_bonded_parity_input


def test_generated_parity_input_has_no_production_nonbonded_model(tmp_path):
    path = tmp_path / "in.pcff_class2"
    write_bonded_parity_input(path, "system.data")
    text = path.read_text(encoding="utf-8")
    assert "pair_style zero" in text
    assert "run 0" in text
    assert "lj/class2" not in text
    assert "pppm" not in text.lower()
