from __future__ import annotations

from .model import *

def _clean_line(line: str) -> str:
    """Remove OFF comments while preserving apostrophes in atom types."""
    return line.split("!", 1)[0].strip()


def _tokens(line: str) -> list[str]:
    return _clean_line(line).split()


def _is_continuation(line: str) -> bool:
    """Continuation rows in this OFF file start with numeric data.

    Torsion and cross-term records use one root row followed by rows such as
    ``1.0000 2.0000 ...``.  A numeric first token is unambiguous here and is
    intentionally not interpreted as a new parameter record.
    """
    toks = _tokens(line)
    return bool(toks) and bool(FLOAT_RE.match(toks[0].replace("D", "E").replace("d", "e")))


def _logical_records(name: str, raw_lines: list[tuple[int, str]]) -> list[OffRecord]:
    records: list[OffRecord] = []
    # STEP_DOWN rows are independent numeric records.  They look like the
    # numeric continuation rows used by Fourier terms, but a Q1/Q2/Q3 token
    # terminates each row and must remain visible as a separate OFF rule.
    if name.startswith("STEP_DOWN"):
        for lineno, line in raw_lines:
            clean = _clean_line(line)
            if not clean or clean == "END":
                continue
            records.append(OffRecord(name, lineno, [line.rstrip("\n")], clean.split()))
        return records

    current: Optional[OffRecord] = None
    for lineno, line in raw_lines:
        clean = _clean_line(line)
        if not clean or clean == "END":
            continue
        toks = clean.split()
        if current is not None and _is_continuation(line):
            current.raw_lines.append(line.rstrip("\n"))
            current.tokens.extend(toks)
            continue
        if current is not None:
            records.append(current)
        current = OffRecord(name, lineno, [line.rstrip("\n")], toks)
    if current is not None:
        records.append(current)
    return records


def parse_off(path: Path) -> list[OffSection]:
    """Parse hash-delimited Materials Studio OFF sections losslessly."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)
    sections: list[OffSection] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "#":
            i += 1
            continue
        marker_line = i + 1
        j = i + 1
        name: Optional[str] = None
        while j < len(lines):
            candidate = _clean_line(lines[j])
            if candidate:
                if SECTION_RE.match(candidate):
                    name = candidate
                break
            j += 1
        if name is None:
            i += 1
            continue
        k = j + 1
        while k < len(lines) and lines[k].strip() != "#":
            k += 1
        payload = [(n + 1, lines[n]) for n in range(j + 1, k)]
        sections.append(
            OffSection(
                name=name,
                start_line=marker_line,
                end_line=k,
                raw_lines=[line.rstrip("\n") for _, line in payload],
                records=_logical_records(name, payload),
            )
        )
        i = k
    return sections


def _as_float(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def _parse_car(path: Path) -> tuple[dict[str, Atom], Optional[tuple[float, float, float, float, float, float]], bool]:
    """Read the atom and cell records from a Materials Studio CAR file."""
    atoms: dict[str, Atom] = {}
    cell: Optional[tuple[float, float, float, float, float, float]] = None
    pbc = False
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        upper = stripped.upper()
        if upper.startswith("PBC="):
            pbc = upper.split("=", 1)[1].strip() == "ON"
            continue
        if upper.startswith("PBC "):
            fields = stripped.split()
            if len(fields) >= 7:
                try:
                    cell = tuple(_as_float(x) for x in fields[1:7])  # type: ignore[assignment]
                    pbc = True
                except ValueError:
                    pass
            continue
        if stripped.lower() == "end":
            continue
        fields = stripped.split()
        if len(fields) < 9:
            continue
        try:
            x, y, z = (_as_float(fields[i]) for i in (1, 2, 3))
            charge = _as_float(fields[8])
        except (IndexError, ValueError):
            continue
        name = fields[0]
        if name in atoms:
            raise ValueError(f"duplicate CAR atom name {name!r} at line {line_no}")
        atoms[name] = Atom(
            id=len(atoms) + 1,
            name=name,
            element=fields[7],
            ms_type=fields[6],
            charge=charge,
            x=x,
            y=y,
            z=z,
        )
    if not atoms:
        raise ValueError(f"no atom records found in CAR: {path}")
    return atoms, cell, pbc


def _connection_token(token: str) -> tuple[str, float]:
    fields = token.split("/", 1)
    if len(fields) == 1:
        return fields[0], 1.0
    return fields[0], _as_float(fields[1])


def parse_molecular_system(car_path: Path, mdf_path: Path) -> MolecularSystem:
    """Read one current PAAm structure without inferring any bonds."""
    car_atoms, cell, pbc = _parse_car(car_path)
    mdf_lines = mdf_path.read_text(encoding="utf-8", errors="replace").splitlines()
    in_molecule = False
    mdf_atoms: list[tuple[str, str, str, float, list[str]]] = []
    for line_no, line in enumerate(mdf_lines, 1):
        stripped = line.strip()
        if stripped.lower().startswith("@molecule"):
            in_molecule = True
            continue
        if not in_molecule or not stripped or stripped.startswith("!"):
            continue
        if stripped.lower() == "#end":
            break
        if stripped.startswith("#") or stripped.startswith("@"):
            continue
        fields = stripped.split()
        if len(fields) < 13 or ":" not in fields[0]:
            continue
        name = fields[0].split(":", 1)[1]
        try:
            element = fields[1]
            ms_type = fields[2]
            charge = _as_float(fields[6])
            connections = fields[12:]
        except (IndexError, ValueError) as exc:
            raise ValueError(f"cannot parse MDF atom at line {line_no}: {line}") from exc
        mdf_atoms.append((name, element, ms_type, charge, connections))
    if not mdf_atoms:
        raise ValueError(f"no molecule atom records found in MDF: {mdf_path}")

    atoms: dict[int, Atom] = {}
    name_to_id: dict[str, int] = {}
    for atom_id, (name, element, ms_type, charge, _) in enumerate(mdf_atoms, 1):
        if name in name_to_id:
            raise ValueError(f"duplicate MDF atom name {name!r}")
        if name not in car_atoms:
            raise ValueError(f"MDF atom {name!r} is absent from CAR")
        car_atom = car_atoms[name]
        if car_atom.element != element:
            raise ValueError(f"element mismatch for {name}: CAR={car_atom.element} MDF={element}")
        atoms[atom_id] = Atom(
            id=atom_id,
            name=name,
            element=element,
            ms_type=ms_type,
            charge=charge,
            x=car_atom.x,
            y=car_atom.y,
            z=car_atom.z,
        )
        name_to_id[name] = atom_id
    if set(car_atoms) != set(name_to_id):
        missing = sorted(set(car_atoms) - set(name_to_id))
        extra = sorted(set(name_to_id) - set(car_atoms))
        raise ValueError(f"CAR/MDF atom-name mismatch; missing_in_MDF={missing} extra_in_MDF={extra}")

    bonds_by_pair: dict[tuple[int, int], float] = {}
    for name, _, _, _, connections in mdf_atoms:
        i = name_to_id[name]
        for connection in connections:
            other_name, order = _connection_token(connection)
            if other_name not in name_to_id:
                raise ValueError(f"MDF connection {name}->{other_name} references no atom")
            j = name_to_id[other_name]
            if i == j:
                raise ValueError(f"MDF self-connection on atom {name}")
            pair = (i, j) if i < j else (j, i)
            old = bonds_by_pair.get(pair)
            if old is not None and not math.isclose(old, order, rel_tol=0.0, abs_tol=1e-8):
                raise ValueError(f"conflicting bond orders for atom pair {pair}: {old} vs {order}")
            bonds_by_pair[pair] = order
    bonds = [Bond(idx, i, j, order) for idx, ((i, j), order) in enumerate(sorted(bonds_by_pair.items()), 1)]
    return MolecularSystem(atoms=atoms, bonds=bonds, cell=cell, pbc=pbc)


def _neighbors(system: MolecularSystem) -> dict[int, list[int]]:
    result = {atom_id: [] for atom_id in system.atoms}
    for bond in system.bonds:
        result[bond.i].append(bond.j)
        result[bond.j].append(bond.i)
    for values in result.values():
        values.sort()
    return result


# The following mapping is the one selected by the read-only global
# cross-geometry identification.  It is intentionally explicit: this module
# must not silently fall back to the old inversion/OOP lookup for Bend-Bend.
NATIVE_BENDBEND_MAPPING = {
    "M1": (1, 0, 3, 2),  # (J,I,L,K) on the official M1 tuple
    "M2": (1, 3, 0, 2),  # (J,L,I,K) on the official M2 tuple
    "M3": (1, 0, 3, 2),  # (J,I,L,K) on the official M3 tuple
}
NATIVE_BENDBEND_SYMMETRY = {
    ("c", "c_1", "c", "h"): ("c", "c", "c_1", "h"),
}
NATIVE_BENDBEND_NOOP_KEYS = {
    ("c", "c", "c", "c_1"),
    ("c", "c", "c_1", "c"),
    ("c", "c_1", "c", "c"),
}
NATIVE_BENDBEND_LINE_OFFSET = 1_000_000
GET_EQUIVS_5_BENDBEND = {
    "c1": "c",
    "c2": "c",
    "c3": "c",
    "c_1": "c_1",
    "o_1": "o_1",
    "n_2": "n_2",
    "hc": "h",
    "hn2": "hn2",
}


def official_angleangle_topology(system: MolecularSystem) -> list[tuple[int, int, int, int]]:
    """Reproduce the confirmed msi2lmp AngleAngle list construction.

    Every atom with coordination greater than three contributes C(n,3)
    records.  The outer atoms are sorted by the original atom-type ordering;
    the center remains in the second position.  For the present PAAm
    pentamer this yields 40 records from ten degree-4 centers.
    """
    neighbors = _neighbors(system)
    type_order: dict[str, int] = {}
    for atom_id in sorted(system.atoms):
        type_order.setdefault(system.atoms[atom_id].ms_type, len(type_order))
    result: list[tuple[int, int, int, int]] = []
    for center in sorted(neighbors):
        connected = neighbors[center]
        if len(connected) <= 3:
            continue
        for outer_ids in itertools.combinations(connected, 3):
            outer = tuple(sorted(
                outer_ids,
                key=lambda atom_id: (
                    type_order[system.atoms[atom_id].ms_type],
                    atom_id,
                ),
            ))
            result.append((outer[0], center, outer[1], outer[2]))
    return result


def native_bendbend_records(path: Path) -> dict[tuple[str, ...], dict[str, str]]:
    """Read the 269 raw native Forcite records without equivalence expansion."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 269:
        raise ValueError(f"expected 269 native Bend-Bend records, found {len(rows)}")
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(row[f"sequence_type{i}"] for i in range(1, 5))
        if key in result:
            raise ValueError(f"duplicate raw native Bend-Bend sequence: {' '.join(key)}")
        result[key] = row
    return result


def _native_bendbend_synthetic_parameters(
    records: dict[tuple[str, ...], dict[str, str]],
) -> list[OffParameter]:
    """Represent native K0 values as writer-resolvable THETA2 records.

    These are source records from the native CSV, not values from pcff.frc or
    fitted values.  A private synthetic line range lets the existing data
    writer resolve the exact record named in each audit row.
    """
    result: list[OffParameter] = []
    for key, row in records.items():
        record_id = int(row["record_id"])
        line = NATIVE_BENDBEND_LINE_OFFSET + record_id
        raw = " ".join((*key, "THETA2", row["K0"]))
        record = OffRecord("BEND_BEND", line, [raw], raw.split())
        result.append(
            OffParameter(
                section="BEND_BEND",
                types=key,
                form="THETA2",
                values=(row["K0"],),
                record=record,
            )
        )
    return result


def add_native_bendbend_parameters(
    parameters: dict[str, list[OffParameter]],
    records: dict[tuple[str, ...], dict[str, str]],
) -> dict[str, list[OffParameter]]:
    """Return parsed OFF parameters plus native Bend-Bend source records."""
    result = {name: list(values) for name, values in parameters.items()}
    result.setdefault("BEND_BEND", []).extend(_native_bendbend_synthetic_parameters(records))
    return result


def _official_angleangle_component_ids(
    ids: tuple[int, int, int, int], component: str
) -> tuple[int, int, int, int]:
    a, b, c, d = ids
    return {
        "M1": (a, b, c, d),
        "M2": (d, b, a, c),
        "M3": (a, b, d, c),
    }[component]


def audit_native_bendbend(
    system: MolecularSystem,
    records: dict[tuple[str, ...], dict[str, str]],
) -> list[AuditRow]:
    """Audit official AngleAngle topology against native records only.

    The only non-exact resolution is the one validated symmetry mapping in
    ``NATIVE_BENDBEND_SYMMETRY``.  Only the three validated ordered keys may
    become K=0 no-ops; every other absent key is fatal.
    """
    rows: list[AuditRow] = []
    for topology_id, ids in enumerate(official_angleangle_topology(system), 1):
        for component in ("M1", "M2", "M3"):
            component_ids = _official_angleangle_component_ids(ids, component)
            original_types = tuple(system.atoms[atom_id].ms_type for atom_id in component_ids)
            query = tuple(GET_EQUIVS_5_BENDBEND[value] for value in original_types)
            permutation = NATIVE_BENDBEND_MAPPING[component]
            lookup_key = tuple(query[index] for index in permutation)
            record = records.get(lookup_key)
            source = "NATIVE_BENDBEND_EXACT"
            matched_key = lookup_key
            if record is None and lookup_key in NATIVE_BENDBEND_SYMMETRY:
                matched_key = NATIVE_BENDBEND_SYMMETRY[lookup_key]
                record = records.get(matched_key)
                source = "NATIVE_BENDBEND_SYMMETRY"
                if record is None:
                    raise ValueError(
                        f"declared native symmetry target is absent: {' '.join(matched_key)}"
                    )
            atom_ids = "-".join(str(atom_id) for atom_id in component_ids)
            common = {
                "interaction": "AngleAngle",
                "atom_ids": atom_ids,
                "ms_atom_types": " ".join(original_types),
            }
            if record is not None:
                record_id = int(record["record_id"])
                line = NATIVE_BENDBEND_LINE_OFFSET + record_id
                detail = (
                    f"BEND_BEND:line {line}: native record {record_id}; "
                    f"sequence={' '.join(matched_key)}; K0={record['K0']}; "
                    f"source={source}; topology={topology_id}; {component}"
                )
                rows.append(AuditRow(
                    **common,
                    match_level=source,
                    matched_off_record=detail,
                    coefficient_values=record["K0"],
                    zero_source="",
                    status="MATCHED",
                ))
                continue
            if lookup_key in NATIVE_BENDBEND_NOOP_KEYS:
                rows.append(AuditRow(
                    **common,
                    match_level="NATIVE_BENDBEND_NOOP",
                    matched_off_record=(
                        "native 269-record set has no raw record for "
                        f"{' '.join(lookup_key)}"
                    ),
                    coefficient_values="0.0",
                    zero_source="NATIVE_BENDBEND_NOOP (validated three-key allowlist)",
                    status=CLASS2_CROSS_ZERO,
                ))
                continue
            rows.append(AuditRow(
                **common,
                match_level="NATIVE_BENDBEND_UNEXPECTED_MISSING",
                matched_off_record=(
                    "native 269-record set has no raw record for "
                    f"{' '.join(lookup_key)}"
                ),
                coefficient_values="",
                zero_source="",
                status=REQUIRED_MISSING,
            ))
    return rows


def molecular_interactions(system: MolecularSystem) -> dict[str, list[tuple[int, ...]]]:
    """Build the actual topology interactions from MDF connectivity only."""
    neighbors = _neighbors(system)
    angles: list[tuple[int, ...]] = []
    for center, bonded in neighbors.items():
        for left, right in itertools.combinations(bonded, 2):
            angles.append((left, center, right))

    dihedrals: list[tuple[int, ...]] = []
    seen_dihedrals: set[tuple[int, ...]] = set()
    for bond in system.bonds:
        for left in neighbors[bond.i]:
            if left == bond.j:
                continue
            for right in neighbors[bond.j]:
                if right == bond.i:
                    continue
                candidate = (left, bond.i, bond.j, right)
                reverse = tuple(reversed(candidate))
                key = min(candidate, reverse)
                if key not in seen_dihedrals:
                    seen_dihedrals.add(key)
                    dihedrals.append(candidate)

    # The Forcite/LAMMPS Class-II topology uses one improper center for each
    # trigonal (three-connected) atom and its three outer permutations.  Do
    # not invent impropers for tetrahedral degree-4 centers.
    impropers: list[tuple[int, ...]] = []
    for center, bonded in neighbors.items():
        if len(bonded) != 3:
            continue
        # OFF INVERSIONS and the Class-II data convention put the central
        # atom first, followed by the three cyclic permutations of its outer
        # neighbors.  Reverse permutations represent the same inversion and
        # are intentionally not duplicated.
        for shift in range(3):
            outer = bonded[shift:] + bonded[:shift]
            impropers.append((center, outer[0], outer[1], outer[2]))
    return {
        "bond": [(bond.i, bond.j) for bond in system.bonds],
        "angle": angles,
        "dihedral": dihedrals,
        "improper": impropers,
    }

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
