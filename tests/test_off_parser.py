from ms_pcff2lammps.converter import parse_off


def test_off_parser_keeps_numeric_continuation_in_logical_record(tmp_path):
    off = tmp_path / "synthetic.txt"
    off.write_text(
        """#
TORSIONS
c c c c DIHEDRAL 1.0 1 1
2.0 2 -1
END
#
"""
    )
    sections = parse_off(off)
    assert len(sections) == 1
    assert sections[0].name == "TORSIONS"
    assert len(sections[0].records) == 1
    assert sections[0].records[0].tokens[-3:] == ["2.0", "2", "-1"]
