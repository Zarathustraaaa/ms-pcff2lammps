from ms_pcff2lammps.converter import (
    Atom,
    Bond,
    CLASS2_CROSS_ZERO,
    MolecularSystem,
    REQUIRED_MISSING,
    _audit_match,
)


def _system():
    atoms = {
        1: Atom(1, "A", "C", "t1", 0.0, 0.0, 0.0, 0.0),
        2: Atom(2, "B", "C", "t2", 0.0, 1.0, 0.0, 0.0),
        3: Atom(3, "C", "C", "t3", 0.0, 2.0, 0.0, 0.0),
    }
    return MolecularSystem(
        atoms=atoms,
        bonds=[Bond(1, 1, 2, 1.0), Bond(2, 2, 3, 1.0)],
        cell=None,
        pbc=False,
    )


def test_unresolved_cross_term_fails_closed_by_default():
    row = _audit_match(
        "BondBond",
        (1, 2, 3),
        _system(),
        [],
        {},
        "angle",
        [],
        {},
        allow_class2_cross_zero=False,
    )
    assert row.status == REQUIRED_MISSING


def test_cross_zero_requires_explicit_opt_in():
    row = _audit_match(
        "BondBond",
        (1, 2, 3),
        _system(),
        [],
        {},
        "angle",
        [],
        {},
        allow_class2_cross_zero=True,
    )
    assert row.status == CLASS2_CROSS_ZERO
