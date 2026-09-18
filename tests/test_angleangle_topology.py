from ms_pcff2lammps.converter import Atom, Bond, MolecularSystem, official_angleangle_topology


def test_degree_four_center_generates_four_angleangle_records():
    atoms = {
        1: Atom(1, "J", "C", "c1", 0.0, 0.0, 0.0, 0.0),
        2: Atom(2, "A", "H", "hc", 0.0, 1.0, 0.0, 0.0),
        3: Atom(3, "B", "C", "c2", 0.0, 0.0, 1.0, 0.0),
        4: Atom(4, "C", "C", "c_1", 0.0, 0.0, 0.0, 1.0),
        5: Atom(5, "D", "H", "hc", 0.0, -1.0, 0.0, 0.0),
    }
    system = MolecularSystem(
        atoms=atoms,
        bonds=[Bond(i, 1, i + 1, 1.0) for i in range(1, 5)],
        cell=None,
        pbc=False,
    )
    rows = official_angleangle_topology(system)
    assert len(rows) == 4
    assert all(row[1] == 1 for row in rows)
    assert len(set(rows)) == 4
