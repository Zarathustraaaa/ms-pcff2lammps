from __future__ import annotations

from .matching import *

def write_audit(path: Path, rows: list[AuditRow]) -> None:
    fields = [
        "interaction",
        "atom_ids",
        "ms_atom_types",
        "match_level",
        "matched_off_record",
        "coefficient_values",
        "zero_source",
        "status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def _parameter_from_audit_row(
    row: AuditRow, parameters: dict[str, list[OffParameter]]
) -> Optional[OffParameter]:
    """Resolve the exact OFF record named in an audit row.

    The audit stores the source line explicitly, so the writer never performs
    a second, potentially different, parameter search.  Zero classifications
    intentionally return ``None`` and are written only through their declared
    Class-II no-op status.
    """
    if row.status == CLASS2_CROSS_ZERO:
        return None
    match = re.search(r":line (\d+):", row.matched_off_record)
    if match is None:
        return None
    line = int(match.group(1))
    section = INTERACTION_SECTION[row.interaction]
    for parameter in parameters.get(section, []):
        if parameter.record.line_start == line:
            return parameter
    raise ValueError(
        f"audit row {row.interaction} {row.atom_ids} references an absent OFF line {section}:{line}"
    )


def _float_values(parameter: Optional[OffParameter]) -> list[float]:
    if parameter is None:
        return []
    try:
        return [_as_float(value) for value in parameter.values]
    except ValueError as exc:
        raise ValueError(
            f"non-numeric coefficient in {parameter.section} line {parameter.record.line_start}"
        ) from exc


def _coefficient_values(
    interaction: str,
    row: AuditRow,
    parameter: Optional[OffParameter],
    reference_values: tuple[float, ...] = (),
) -> list[float]:
    """Translate the already-matched OFF form to LAMMPS Class-II order.

    Only documented rearrangements of the OFF records are performed.  An
    absent cross record is represented by the interaction-specific zero
    vector; a diagonal record without a supported form is an error.
    """
    zero_lengths = {
        "improper": 2,
        "BondBond": 3,
        "BondAngle": 4,
        "BondBond13": 3,
        "MiddleBondTorsion": 4,
        "EndBondTorsion": 8,
        "AngleTorsion": 8,
        "AngleAngleTorsion": 3,
        # One OFF BEND_BEND row supplies one of the three M values.  The
        # writer assembles the three cyclic rows into the six-value LAMMPS
        # AngleAngle record.
        "AngleAngle": 1,
    }
    reversed_match = "[type order reversed]" in row.matched_off_record
    if parameter is None:
        if row.status == "OFF_IGNORE" or row.status == CLASS2_CROSS_ZERO:
            return [0.0] * zero_lengths[interaction]
        raise ValueError(f"required interaction {interaction} {row.atom_ids} has no OFF record")
    if parameter.ignored:
        if interaction not in zero_lengths:
            raise ValueError(f"diagonal interaction {interaction} cannot use OFF IGNORE")
        return [0.0] * zero_lengths[interaction]

    values = _float_values(parameter)
    form = parameter.form.upper()
    if interaction == "bond":
        if form != "QUARTIC" or len(values) < 4:
            raise ValueError(f"unsupported BOND_STRETCH form {parameter.form!r} at line {parameter.record.line_start}")
        # OFF stores QUARTIC as K2, r0, K3/K2, K4/K2.  The LAMMPS
        # Class-II implementation uses the expanded polynomial without the
        # conventional 1/2 prefactor.  Convert the diagonal constants as
        # K2_lammps=K2_off/2 and K3/K4=K2_lammps*(K3/K2,K4/K2).
        # This is a representation conversion, not a new parameter.
        k2 = 0.5 * values[0]
        return [values[1], k2, k2 * values[2], k2 * values[3]]
    if interaction == "angle":
        if form in {"THETA_QUAR", "THETA_QUART"}:
            if len(values) < 4:
                raise ValueError(
                    f"short ANGLE_BEND record at line {parameter.record.line_start}"
                )
            # OFF stores THETA_QUAR as K2, theta0, K3/K2, K4/K2.  Convert
            # to the expanded LAMMPS Class-II coefficients.
            k2 = 0.5 * values[0]
            return [values[1], k2, k2 * values[2], k2 * values[3]]
        if form == "THETA_HARM":
            if len(values) < 2:
                raise ValueError(
                    f"short THETA_HARM record at line {parameter.record.line_start}"
                )
            # OFF harmonic: K theta0.  This is exactly the Class-II
            # polynomial with K2=K and K3=K4=0; no coefficient is invented.
            return [values[1], 0.5 * values[0], 0.0, 0.0]
        raise ValueError(
            f"unsupported ANGLE_BEND form {parameter.form!r} at line "
            f"{parameter.record.line_start}"
        )
    if interaction == "dihedral":
        if form != "DIHEDRAL":
            raise ValueError(f"unsupported TORSIONS form {parameter.form!r} at line {parameter.record.line_start}")
        # Each OFF Fourier triplet is (K, periodicity, phase-factor).  The
        # current PCFF records use the standard n=1/2/3 sequence.  LAMMPS
        # stores (K1,phi1,K2,phi2,K3,phi3); d=+1 maps to 0 degrees and d=-1
        # maps to 180 degrees in 1-cos(n*phi-phi_n).
        result = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        if len(values) % 3:
            raise ValueError(f"malformed DIHEDRAL record at line {parameter.record.line_start}")
        for offset in range(0, len(values), 3):
            coefficient = values[offset]
            periodicity = int(round(values[offset + 1]))
            phase_factor = values[offset + 2]
            # Official PCFF uses (0, 0, -1) as a literal no-op Fourier
            # component in some wildcard torsion records.  It contributes
            # no energy and has no LAMMPS periodicity to encode.
            if math.isclose(coefficient, 0.0, abs_tol=1.0e-12) and periodicity == 0:
                continue
            if periodicity not in {1, 2, 3} or not math.isclose(abs(phase_factor), 1.0, abs_tol=1e-6):
                raise ValueError(
                    f"unsupported DIHEDRAL periodicity/phase at line {parameter.record.line_start}"
                )
            # OFF Fourier amplitudes use the conventional PCFF 1/2
            # prefactor; LAMMPS class2 Ed has no such prefactor.
            result[2 * (periodicity - 1)] = 0.5 * coefficient
            result[2 * (periodicity - 1) + 1] = 0.0 if phase_factor > 0 else 180.0
        return result
    if interaction == "improper":
        if form != "WILSON_AVG" or not values:
            raise ValueError(f"unsupported INVERSIONS form {parameter.form!r} at line {parameter.record.line_start}")
        # Wilson out-of-plane records contain K; PCFF's reference plane is
        # chi0=0 for this LAMMPS Class-II form.
        return [0.5 * values[0], 0.0]

    if interaction in {"AngleAngleTorsion", "AngleAngle"}:
        if not values:
            raise ValueError(f"empty cross-term record at line {parameter.record.line_start}")
        if interaction == "AngleAngleTorsion":
            if len(values) < 1:
                raise ValueError(f"empty AngleAngleTorsion record at line {parameter.record.line_start}")
            return [values[0], *list(reference_values[:2])]
        if form != "THETA2":
            raise ValueError(
                f"unsupported BEND_BEND form {parameter.form!r} at line "
                f"{parameter.record.line_start}"
            )
        # One OFF BEND_BEND row is one M coefficient.  The three cyclic
        # rows are assembled by write_lammps_class2_data into M1/M2/M3.
        return [values[0]]
    if interaction == "BondBond":
        if not values or len(reference_values) < 2:
            raise ValueError(f"BondBond record/reference incomplete at line {parameter.record.line_start}")
        return [values[0], reference_values[0], reference_values[1]]
    if interaction == "BondBond13":
        if not values or len(reference_values) < 2:
            raise ValueError(f"BondBond13 record/reference incomplete at line {parameter.record.line_start}")
        return [values[0], reference_values[0], reference_values[1]]
    if interaction == "BondAngle":
        if len(values) < 2:
            raise ValueError(f"short BondAngle record at line {parameter.record.line_start}")
        if len(reference_values) < 2:
            raise ValueError(f"BondAngle record/reference incomplete at line {parameter.record.line_start}")
        # The OFF record's two coefficients follow its own I-J and J-K
        # order.  If the formal match used the reversed type tuple, swap
        # N1/N2 so they follow the LAMMPS angle's actual I-J/J-K order.
        n1, n2 = values[0], values[1]
        if reversed_match:
            n1, n2 = n2, n1
        return [n1, n2, reference_values[0], reference_values[1]]
    if interaction == "MiddleBondTorsion":
        if form != "R-FOURIER" or len(values) < 3:
            raise ValueError(f"unsupported TORSION_STRETCH form {parameter.form!r} at line {parameter.record.line_start}")
        # OFF: n K1 n K2 n K3.
        if len(values) < 6 or len(reference_values) < 1:
            raise ValueError(f"MiddleBondTorsion record/reference incomplete at line {parameter.record.line_start}")
        return [values[1], values[3], values[5], reference_values[0]]
    if interaction in {"EndBondTorsion", "AngleTorsion"}:
        expected_form = "R-FOURIER" if interaction == "EndBondTorsion" else "THETA-FOUR"
        if form != expected_form or len(values) < 9:
            raise ValueError(f"unsupported {interaction} form {parameter.form!r} at line {parameter.record.line_start}")
        # OFF: n K(left) K(right), repeated for n=1,2,3.  LAMMPS appends
        # the two equilibrium bond/angle values used by the coupling.
        if len(reference_values) < 2:
            raise ValueError(f"{interaction} record/reference incomplete at line {parameter.record.line_start}")
        left = [values[1], values[4], values[7]]
        right = [values[2], values[5], values[8]]
        if reversed_match:
            left, right = right, left
        return [*left, *right, reference_values[0], reference_values[1]]
    raise ValueError(f"unknown Class-II interaction {interaction}")


def _fmt_coefficients(values: Iterable[float]) -> str:
    return " ".join(f"{value:.12g}" for value in values)


def _audit_rows_by_interaction(rows: list[AuditRow]) -> dict[str, list[AuditRow]]:
    result: dict[str, list[AuditRow]] = {}
    for row in rows:
        result.setdefault(row.interaction, []).append(row)
    return result


def _group_improper_cycles(
    interactions: list[tuple[int, ...]],
) -> list[list[tuple[int, ...]]]:
    """Group the three cyclic audit quadruplets into one LAMMPS improper.

    The audit keeps each cyclic BEND_BEND lookup visible because the three
    OFF records map to the three LAMMPS angle-angle coefficients.  The
    LAMMPS topology, however, has one improper quadruplet per central atom;
    its Class-II style evaluates all three out-of-plane/angle-angle branches.
    """
    groups: dict[int, list[tuple[int, ...]]] = {}
    order: list[int] = []
    for ids in interactions:
        if len(ids) != 4:
            raise ValueError(f"improper topology record must have four atoms: {ids}")
        center = ids[0]
        if center not in groups:
            groups[center] = []
            order.append(center)
        groups[center].append(ids)
    result: list[list[tuple[int, ...]]] = []
    for center in order:
        cycles = groups[center]
        if len(cycles) != 3:
            raise ValueError(
                f"improper center {center} has {len(cycles)} cyclic records; "
                "expected exactly 3 for Class-II AngleAngle assembly"
            )
        result.append(cycles)
    return result


def _mass_for_element(element: str) -> float:
    masses = {"H": 1.008, "C": 12.011, "N": 14.007, "O": 15.9994}
    try:
        return masses[element.upper()]
    except KeyError as exc:
        raise ValueError(f"no built-in mass for element {element!r}") from exc

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
