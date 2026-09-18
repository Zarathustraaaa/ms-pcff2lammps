from __future__ import annotations

from .coefficients import *

def write_lammps_class2_data(
    path: Path,
    system: MolecularSystem,
    rows: list[AuditRow],
    parameters: dict[str, list[OffParameter]],
) -> None:
    """Write a fixed-coordinate Class-II data file from the audited rows."""
    interactions = molecular_interactions(system)
    improper_groups = _group_improper_cycles(interactions["improper"])
    by_interaction = _audit_rows_by_interaction(rows)
    # When the final native Forcite record set was supplied to audit_system,
    # AngleAngle rows are the 40 official degree-4 msi2lmp topologies (three
    # M components each), not the historical three cyclic rows per trigonal
    # improper.  Keep the old path intact for older audit-only callers.
    native_mode = any(
        row.interaction == "AngleAngle"
        and row.match_level.startswith("NATIVE_BENDBEND")
        for row in by_interaction.get("AngleAngle", [])
    )
    official_angleangle = official_angleangle_topology(system) if native_mode else []
    improper_entries: list[tuple[int, int, int, int]] = [
        (cycles[0][1], cycles[0][0], cycles[0][2], cycles[0][3])
        for cycles in improper_groups
    ]
    if native_mode:
        # official_angleangle_topology is already (I,J,K,L), with J the
        # central atom.  These entries are separate LAMMPS improper records
        # whose AngleAngle coefficients carry the native Bend-Bend terms.
        improper_entries.extend(official_angleangle)
    improper_count = len(improper_entries)
    required = sum(1 for row in rows if row.status == REQUIRED_MISSING)
    if required:
        raise ValueError(f"refusing to write data with {required} REQUIRED_MISSING rows")

    # Give every topology instance its own type.  This is intentionally
    # verbose, but it preserves each audited OFF match without coalescing
    # records through an unverified equivalence.
    type_ids = {
        name: list(range(1, len(instances) + 1))
        for name, instances in interactions.items()
    }
    type_ids["improper"] = list(range(1, improper_count + 1))
    atom_type_by_ms: dict[str, int] = {}
    for atom in system.atoms.values():
        atom_type_by_ms.setdefault(atom.ms_type, len(atom_type_by_ms) + 1)

    lines: list[str] = [
        "LAMMPS data file: Materials Studio PCFF Class-II fixed-coordinate audit",
        "",
        f"{len(system.atoms)} atoms",
        f"{len(system.bonds)} bonds",
        f"{len(interactions['angle'])} angles",
        f"{len(interactions['dihedral'])} dihedrals",
        f"{improper_count} impropers",
        "",
        f"{len(atom_type_by_ms)} atom types",
        f"{len(interactions['bond'])} bond types",
        f"{len(interactions['angle'])} angle types",
        f"{len(interactions['dihedral'])} dihedral types",
        f"{improper_count} improper types",
        "",
    ]
    xs = [atom.x for atom in system.atoms.values()]
    ys = [atom.y for atom in system.atoms.values()]
    zs = [atom.z for atom in system.atoms.values()]
    pad = 1.0
    lines.extend([
        f"{min(xs) - pad:.12g} {max(xs) + pad:.12g} xlo xhi",
        f"{min(ys) - pad:.12g} {max(ys) + pad:.12g} ylo yhi",
        f"{min(zs) - pad:.12g} {max(zs) + pad:.12g} zlo zhi",
        "",
        "Masses",
        "",
    ])
    for ms_type, atom_type in atom_type_by_ms.items():
        atom = next(atom for atom in system.atoms.values() if atom.ms_type == ms_type)
        lines.append(f"{atom_type:6d} {_mass_for_element(atom.element):.8f} # {ms_type}")

    bond_rows = by_interaction["bond"]
    angle_rows = by_interaction["angle"]
    dihedral_rows = by_interaction["dihedral"]
    improper_rows = by_interaction["improper"]
    if len(improper_rows) != 3 * len(improper_groups):
        raise ValueError(
            f"audit row count for improper is {len(improper_rows)}, expected "
            f"{3 * len(improper_groups)} cyclic records"
        )
    improper_base_rows = [improper_rows[index * 3] for index in range(len(improper_groups))]
    if native_mode:
        # The official degree-4 records are AngleAngle-only.  Their ordinary
        # inversion coefficient is an explicit internal no-op, not a missing
        # parameter and not a value copied from another force field.
        native_improper_zero_rows = [
            AuditRow(
                interaction="improper",
                atom_ids="-".join(str(atom_id) for atom_id in ids),
                ms_atom_types=" ".join(system.atoms[atom_id].ms_type for atom_id in ids),
                match_level="NATIVE_BENDBEND_IMPROPER_NOOP",
                matched_off_record="",
                coefficient_values="0.0 0.0",
                zero_source="official degree-4 AngleAngle entry has no inversion term",
                status=CLASS2_CROSS_ZERO,
            )
            for ids in official_angleangle
        ]
        improper_coeff_rows = improper_base_rows + native_improper_zero_rows
    else:
        improper_coeff_rows = improper_base_rows
    bond_coeffs = [
        _coefficient_values("bond", row, _parameter_from_audit_row(row, parameters))
        for row in bond_rows
    ]
    angle_coeffs = [
        _coefficient_values("angle", row, _parameter_from_audit_row(row, parameters))
        for row in angle_rows
    ]

    def pair_key(i: int, j: int) -> tuple[int, int]:
        return (i, j) if i < j else (j, i)

    bond_r0: dict[tuple[int, int], float] = {
        pair_key(bond.i, bond.j): bond_coeffs[index][0]
        for index, bond in enumerate(system.bonds)
    }

    def angle_key(ids: tuple[int, int, int]) -> tuple[int, int, int]:
        left, center, right = ids
        return center, min(left, right), max(left, right)

    theta0: dict[tuple[int, int, int], float] = {
        angle_key(ids): angle_coeffs[index][0]
        for index, ids in enumerate(interactions["angle"])
    }

    angle_reference_values = [
        (
            bond_r0[pair_key(ids[0], ids[1])],
            bond_r0[pair_key(ids[1], ids[2])],
        )
        for ids in interactions["angle"]
    ]
    dihedral_mbt_refs = [
        (bond_r0[pair_key(ids[1], ids[2])],)
        for ids in interactions["dihedral"]
    ]
    dihedral_ebt_refs = [
        (bond_r0[pair_key(ids[0], ids[1])], bond_r0[pair_key(ids[2], ids[3])])
        for ids in interactions["dihedral"]
    ]
    dihedral_angle_refs = [
        (
            theta0[angle_key((ids[0], ids[1], ids[2]))],
            theta0[angle_key((ids[1], ids[2], ids[3]))],
        )
        for ids in interactions["dihedral"]
    ]
    improper_angle_refs = []
    for cycles in improper_groups:
        center, outer0, outer1, outer2 = cycles[0]
        # LAMMPS orders an improper as I,J,K,L with J as the symmetry atom.
        # Its Class-II implementation requires theta0 in the source order
        # theta1=ABC, theta2=ABD, theta3=CBD.  The native M1/M2/M3 values
        # already correspond to the three products in that implementation.
        improper_angle_refs.append(
            (
                theta0[angle_key((outer0, center, outer1))],
                theta0[angle_key((outer0, center, outer2))],
                theta0[angle_key((outer1, center, outer2))],
            )
        )

    official_angleangle_refs: list[tuple[float, float, float]] = []
    for a, b, c, d in official_angleangle:
        # Keep the exact LAMMPS Class-II order: theta1=ABC, theta2=ABD,
        # theta3=CBD.  Here b is the central atom J.
        official_angleangle_refs.append(
            (
                theta0[angle_key((a, b, c))],
                theta0[angle_key((a, b, d))],
                theta0[angle_key((c, b, d))],
            )
        )

    def coeff_section(
        title: str,
        interaction: str,
        rows_for_terms: list[AuditRow],
        count: int,
        references: Optional[list[tuple[float, ...]]] = None,
    ) -> None:
        lines.extend(["", title, ""])
        if len(rows_for_terms) != count:
            raise ValueError(
                f"audit row count for {interaction} is {len(rows_for_terms)}, expected {count}"
            )
        for index, row in enumerate(rows_for_terms, 1):
            parameter = _parameter_from_audit_row(row, parameters)
            reference_values = () if references is None else references[index - 1]
            values = _coefficient_values(interaction, row, parameter, reference_values)
            lines.append(
                f"{index:6d} {_fmt_coefficients(values)} # {row.ms_atom_types} [{row.status}]"
            )

    coeff_section("Bond Coeffs # class2", "bond", bond_rows, len(interactions["bond"]))
    coeff_section("Angle Coeffs # class2", "angle", angle_rows, len(interactions["angle"]))
    coeff_section("Dihedral Coeffs # class2", "dihedral", dihedral_rows, len(interactions["dihedral"]))
    coeff_section("Improper Coeffs # class2", "improper", improper_coeff_rows, improper_count)
    coeff_section(
        "BondBond Coeffs", "BondBond", by_interaction["BondBond"],
        len(interactions["angle"]), angle_reference_values,
    )
    coeff_section(
        "BondAngle Coeffs", "BondAngle", by_interaction["BondAngle"],
        len(interactions["angle"]), angle_reference_values,
    )
    coeff_section("BondBond13 Coeffs", "BondBond13", [
        AuditRow("BondBond13", "", "", "CLASS2_CROSS_ABSENT", "", "0", "", CLASS2_CROSS_ZERO)
        for _ in interactions["dihedral"]
    ], len(interactions["dihedral"]))
    coeff_section(
        "MiddleBondTorsion Coeffs", "MiddleBondTorsion", by_interaction["MiddleBondTorsion"],
        len(interactions["dihedral"]), dihedral_mbt_refs,
    )
    coeff_section(
        "EndBondTorsion Coeffs", "EndBondTorsion", by_interaction["EndBondTorsion"],
        len(interactions["dihedral"]), dihedral_ebt_refs,
    )
    coeff_section(
        "AngleTorsion Coeffs", "AngleTorsion", by_interaction["AngleTorsion"],
        len(interactions["dihedral"]), dihedral_angle_refs,
    )
    coeff_section(
        "AngleAngleTorsion Coeffs", "AngleAngleTorsion", by_interaction["AngleAngleTorsion"],
        len(interactions["dihedral"]), dihedral_angle_refs,
    )
    angle_angle_rows = by_interaction["AngleAngle"]
    lines.extend(["", "AngleAngle Coeffs", ""])
    if native_mode:
        if len(angle_angle_rows) != 3 * len(official_angleangle):
            raise ValueError(
                f"native AngleAngle audit has {len(angle_angle_rows)} rows, expected "
                f"{3 * len(official_angleangle)} official components"
            )
        # The first entries are the existing trigonal inversion records.  A
        # zero AngleAngle vector keeps their ordinary improper entry
        # separate; the native Bend-Bend entries follow as official degree-4
        # AngleAngle topology records.
        for index, cycles in enumerate(improper_groups):
            references = improper_angle_refs[index]
            lines.append(
                f"{index + 1:6d} 0 0 0 {_fmt_coefficients(references)} # "
                f"inversion AngleAngle [NATIVE_BENDBEND_IMPROPER_NOOP]"
            )
        start_type = len(improper_groups)
        for index, ids in enumerate(official_angleangle):
            row0, row1, row2 = angle_angle_rows[index * 3:index * 3 + 3]
            m_values: list[float] = []
            for row in (row0, row1, row2):
                parameter = _parameter_from_audit_row(row, parameters)
                values = _coefficient_values("AngleAngle", row, parameter)
                if len(values) != 1:
                    raise ValueError(
                        f"native BEND_BEND row {row.atom_ids} did not yield one M coefficient"
                    )
                m_values.append(values[0])
            values = [*m_values, *official_angleangle_refs[index]]
            statuses = "/".join(row.status for row in (row0, row1, row2))
            lines.append(
                f"{start_type + index + 1:6d} {_fmt_coefficients(values)} # "
                f"{' '.join(system.atoms[atom_id].ms_type for atom_id in ids)} [{statuses}]"
            )
    else:
        # Historical mode: each trigonal center contributes three cyclic OFF
        # BEND_BEND lookups, assembled into one LAMMPS improper type.
        if len(angle_angle_rows) != 3 * len(improper_groups):
            raise ValueError(
                f"audit row count for AngleAngle is {len(angle_angle_rows)}, expected "
                f"{3 * len(improper_groups)} cyclic records"
            )
        for index, cycles in enumerate(improper_groups):
            row0, row1, row2 = angle_angle_rows[index * 3:index * 3 + 3]
            cycle_rows = (row0, row1, row2)
            m_values: list[float] = []
            # OFF cycle 0 -> M1, cycle 2 -> M2, cycle 1 -> M3.
            for cycle_index in (0, 2, 1):
                row = cycle_rows[cycle_index]
                parameter = _parameter_from_audit_row(row, parameters)
                values = _coefficient_values("AngleAngle", row, parameter)
                if len(values) != 1:
                    raise ValueError(
                        f"BEND_BEND row {row.atom_ids} did not yield one M coefficient"
                    )
                m_values.append(values[0])
            references = improper_angle_refs[index]
            values = [*m_values, *references]
            statuses = "/".join(row.status for row in cycle_rows)
            lines.append(
                f"{index + 1:6d} {_fmt_coefficients(values)} # "
                f"{cycle_rows[0].ms_atom_types} [{statuses}]"
            )

    lines.extend(["", "Atoms # full", ""])
    for atom in system.atoms.values():
        lines.append(
            f"{atom.id:6d} 1 {atom_type_by_ms[atom.ms_type]:4d} {atom.charge: .12g} "
            f"{atom.x: .12g} {atom.y: .12g} {atom.z: .12g} # {atom.ms_type}"
        )
    lines.extend(["", "Bonds", ""])
    for index, bond in enumerate(system.bonds, 1):
        lines.append(f"{index:6d} {type_ids['bond'][index - 1]:6d} {bond.i:6d} {bond.j:6d}")
    lines.extend(["", "Angles", ""])
    for index, (left, center, right) in enumerate(interactions["angle"], 1):
        lines.append(f"{index:6d} {type_ids['angle'][index - 1]:6d} {left:6d} {center:6d} {right:6d}")
    lines.extend(["", "Dihedrals", ""])
    for index, ids in enumerate(interactions["dihedral"], 1):
        lines.append(f"{index:6d} {type_ids['dihedral'][index - 1]:6d} {' '.join(f'{value:6d}' for value in ids)}")
    lines.extend(["", "Impropers", ""])
    for index, lammps_ids in enumerate(improper_entries, 1):
        lines.append(
            f"{index:6d} {type_ids['improper'][index - 1]:6d} "
            f"{' '.join(f'{value:6d}' for value in lammps_ids)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_bonded_parity_input(path: Path, data_name: str = "pcff_class2.data") -> None:
    path.write_text(
        "\n".join([
            "# Fixed-coordinate PCFF Class-II bonded audit; no minimization",
            "units real",
            "atom_style full",
            "boundary f f f",
            "pair_style zero 1.0",
            "bond_style class2",
            "angle_style class2",
            "dihedral_style class2",
            "improper_style class2",
            f"read_data {data_name}",
            "pair_coeff * *",
            "thermo 1",
            "thermo_style custom step pe ebond eangle edihed eimp etotal",
            "thermo_modify format float %20.15g",
            "run 0",
            "",
        ])
        , encoding="utf-8",
    )

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
