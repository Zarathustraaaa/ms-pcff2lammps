from __future__ import annotations

from .lookup import *

def _atom_type_string(system: MolecularSystem, ids: Iterable[int]) -> tuple[str, ...]:
    return tuple(system.atoms[atom_id].ms_type for atom_id in ids)


def _bond_order_for_pair(system: MolecularSystem, i: int, j: int) -> float:
    pair = (i, j) if i < j else (j, i)
    for bond in system.bonds:
        if (bond.i, bond.j) == pair:
            return bond.order
    raise ValueError(f"no MDF bond found for pair {i}-{j}")


def _interaction_bond_orders(
    system: MolecularSystem, ids: tuple[int, ...], interaction: str
) -> tuple[float, ...]:
    """Return the MDF bond orders needed by an OFF step-down pattern."""
    if interaction == "nonbond":
        return ()
    if interaction == "improper" or interaction == "AngleAngle":
        center = ids[0]
        return tuple(_bond_order_for_pair(system, center, outer) for outer in ids[1:])
    return tuple(
        _bond_order_for_pair(system, ids[index], ids[index + 1])
        for index in range(len(ids) - 1)
    )


def _interaction_bond_pairs(ids: tuple[int, ...], interaction: str) -> tuple[tuple[int, int], ...]:
    """Return the atom pairs represented by an interaction's bond ranks."""
    if interaction == "nonbond":
        return ()
    if interaction in {"improper", "AngleAngle"}:
        center = ids[0]
        return tuple((center, outer) for outer in ids[1:])
    return tuple((ids[index], ids[index + 1]) for index in range(len(ids) - 1))


def _audit_match(
    interaction: str,
    ids: tuple[int, ...],
    system: MolecularSystem,
    parameters: list[OffParameter],
    equivalence: dict[str, dict[str, EquivalenceRule]],
    scheme: str,
    step_down_rules: list[StepDownRule],
    bond_type_rules: dict[str, BondTypeEquivalenceRule],
    allow_class2_cross_zero: bool = False,
) -> AuditRow:
    requested = _atom_type_string(system, ids)
    bond_orders = _interaction_bond_orders(system, ids, interaction)
    parameter, how, reversed_order = find_parameter(
        requested,
        parameters,
        equivalence,
        scheme=scheme,
        step_down_rules=step_down_rules,
        bond_orders=bond_orders,
        bond_type_rules=bond_type_rules,
    )
    if parameter is None:
        if interaction in CLASS2_CROSS_INTERACTIONS and allow_class2_cross_zero:
            return AuditRow(
                interaction=interaction,
                atom_ids="-".join(str(atom_id) for atom_id in ids),
                ms_atom_types=" ".join(requested),
                match_level="CLASS2_CROSS_ABSENT",
                matched_off_record=(
                    "no matching OFF record after formal exact/equivalence/step-down/X search"
                ),
                coefficient_values="0",
                zero_source=(
                    "Forcite ground truth: Automatic parameters=0; Missing parameters=0"
                ),
                status=CLASS2_CROSS_ZERO,
            )
        return AuditRow(
            interaction=interaction,
            atom_ids="-".join(str(atom_id) for atom_id in ids),
            ms_atom_types=" ".join(requested),
            match_level="MISSING",
            matched_off_record="",
            coefficient_values="",
            zero_source="",
            status=REQUIRED_MISSING,
        )
    if parameter.ignored:
        detail = _format_record(parameter) + " [explicit OFF IGNORE]"
        if how not in {"exact", "symmetry"}:
            detail += f" [via {how}]"
        return AuditRow(
            interaction=interaction,
            atom_ids="-".join(str(atom_id) for atom_id in ids),
            ms_atom_types=" ".join(requested),
            match_level="IGNORE",
            matched_off_record=detail,
            coefficient_values="0",
            zero_source="explicit OFF IGNORE",
            status="OFF_IGNORE",
        )
    detail = _format_record(parameter)
    if how.startswith("equivalence"):
        detail = f"{detail} [OFF equivalence]"
    if "X" in parameter.types:
        detail = f"{detail} [explicit OFF X wildcard]"
    if reversed_order:
        detail = f"{detail} [type order reversed]"
    return AuditRow(
        interaction=interaction,
        atom_ids="-".join(str(atom_id) for atom_id in ids),
        ms_atom_types=" ".join(requested),
        match_level=how,
        matched_off_record=detail,
        coefficient_values=" ".join(parameter.values),
        zero_source="",
        status="MATCHED",
    )


def audit_system(
    system: MolecularSystem,
    sections: list[OffSection],
    *,
    forcite_missing_parameters: Optional[int] = None,
    allow_forcite_cross_zero: bool = False,
    native_bendbend: Optional[dict[tuple[str, ...], dict[str, str]]] = None,
    bendbend_profile: Optional[str] = None,
) -> list[AuditRow]:
    """Audit OFF terms using a fail-closed parameter policy.

    Missing diagonal terms are always fatal. An unresolved Class-II cross term
    may be recorded as a no-op only when both ``allow_forcite_cross_zero`` is
    true and the caller explicitly asserts ``forcite_missing_parameters=0`` for
    the same structure. Native Bend-Bend records additionally require a named
    validated mapping profile.
    """
    if allow_forcite_cross_zero and forcite_missing_parameters != 0:
        raise ValueError(
            "--allow-forcite-cross-zero requires --forcite-missing-parameters 0"
        )
    if native_bendbend is not None:
        if bendbend_profile not in BEND_BEND_PROFILES:
            raise ValueError(
                "native Bend-Bend conversion requires an explicit validated "
                "--bendbend-profile; available profile: paam-pentamer-20260917"
            )
    elif bendbend_profile is not None:
        raise ValueError("--bendbend-profile requires --native-bendbend")
    parameters = parse_parameters(sections)
    bond_type_rules = parse_bond_type_equivalence(sections)
    interactions = molecular_interactions(system)
    rows: list[AuditRow] = []
    allow_class2_cross_zero = allow_forcite_cross_zero and forcite_missing_parameters == 0

    vdw_equivalence = parse_equivalences(sections, "EQUIVALENCE_OFF_DIAGONAL_VDW")
    vdw_step_down = parse_step_down(sections, "STEP_DOWN_OFF_DIAGONAL_VDW")
    for atom_id in sorted(system.atoms):
        rows.append(
            _audit_match(
                "nonbond", (atom_id,), system, parameters["DIAGONAL_VDW"], vdw_equivalence,
                "all", vdw_step_down, bond_type_rules,
                allow_class2_cross_zero=allow_class2_cross_zero,
            )
        )

    bond_equivalence = parse_equivalences(sections, "EQUIVALENCE_BOND")
    bond_step_down = parse_step_down(sections, "STEP_DOWN_BOND")
    for ids in interactions["bond"]:
        rows.append(
            _audit_match(
                "bond", ids, system, parameters["BOND_STRETCH"], bond_equivalence,
                "bond", bond_step_down, bond_type_rules,
            )
        )

    angle_equivalence = parse_equivalences(sections, "EQUIVALENCE_ANGLE")
    angle_step_down = parse_step_down(sections, "STEP_DOWN_ANGLE")
    for ids in interactions["angle"]:
        for interaction, section_name in (
            ("angle", "ANGLE_BEND"),
            ("BondBond", "STRETCH_STRETCH"),
            ("BondAngle", "STRETCH_BEND_STRETCH"),
        ):
            rows.append(
                _audit_match(
                    interaction, ids, system, parameters[section_name], angle_equivalence,
                    "angle", angle_step_down, bond_type_rules,
                    allow_class2_cross_zero=allow_class2_cross_zero,
                )
            )

    torsion_equivalence = parse_equivalences(sections, "EQUIVALENCE_TORSION")
    torsion_step_down = parse_step_down(sections, "STEP_DOWN_TORSION")
    for ids in interactions["dihedral"]:
        for interaction, section_name in (
            ("dihedral", "TORSIONS"),
            ("MiddleBondTorsion", "TORSION_STRETCH"),
            ("EndBondTorsion", "STRETCH_TORSION_STRETCH"),
        ):
            rows.append(
                _audit_match(
                    interaction, ids, system, parameters[section_name], torsion_equivalence,
                    "torsion", torsion_step_down, bond_type_rules,
                    allow_class2_cross_zero=allow_class2_cross_zero,
                )
            )
        # The official separated stretch-stretch table is a conjugated (cp)
        # interaction.  This all-sp3 PAAm pentamer contains no cp/c5 type, so
        # BondBond13 is not a required term for this structure.
        if "cp" in _atom_type_string(system, ids):
            rows.append(
                _audit_match(
                    "BondBond13", ids, system, parameters["SEPARATED_STRETCH_STRETCH"],
                    torsion_equivalence, "torsion", torsion_step_down, bond_type_rules,
                    allow_class2_cross_zero=allow_class2_cross_zero,
                )
            )
        for interaction, section_name in (
            ("AngleTorsion", "BEND_TORSION_BEND"),
            ("AngleAngleTorsion", "TORSION_BEND_BEND"),
        ):
            rows.append(
                _audit_match(
                    interaction, ids, system, parameters[section_name], torsion_equivalence,
                    "torsion", torsion_step_down, bond_type_rules,
                    allow_class2_cross_zero=allow_class2_cross_zero,
                )
            )

    inversion_equivalence = parse_equivalences(sections, "EQUIVALENCE_INVERSION")
    inversion_step_down = parse_step_down(sections, "STEP_DOWN_INVERSION")
    for ids in interactions["improper"]:
        rows.append(
            _audit_match(
                "improper", ids, system, parameters["INVERSIONS"], inversion_equivalence,
                "inversion", inversion_step_down, bond_type_rules,
            )
        )

    if native_bendbend is None:
        # Generic OFF-backed AngleAngle audit path. The native Bend-Bend mapping
        # below is reserved for explicitly named validation profiles.
        for ids in interactions["improper"]:
            rows.append(
                _audit_match(
                    "AngleAngle", ids, system, parameters["BEND_BEND"], inversion_equivalence,
                    "inversion", inversion_step_down, bond_type_rules,
                    allow_class2_cross_zero=allow_class2_cross_zero,
                )
            )
    else:
        rows.extend(audit_native_bendbend(system, native_bendbend))
    return rows


def _first_parameter_for_queries(
    parameters: list[OffParameter],
    queries: Iterable[SearchQuery],
    ignored: bool,
) -> Optional[OffParameter]:
    """Return the first exact-type record in an already-built query layer."""
    by_types: dict[tuple[str, ...], list[OffParameter]] = {}
    for parameter in parameters:
        by_types.setdefault(parameter.types, []).append(parameter)
    for candidate in queries:
        for parameter in by_types.get(candidate.query, []):
            if parameter.ignored == ignored:
                return parameter
    return None


def _first_generic_parameter(
    parameters: list[OffParameter],
    queries: Iterable[SearchQuery],
    ignored: bool,
) -> Optional[OffParameter]:
    """Find an existing OFF wildcard record, without creating one."""
    matches: list[tuple[OffParameter, int]] = []
    for candidate in queries:
        for parameter in parameters:
            if parameter.ignored != ignored or "X" not in parameter.types:
                continue
            if _parameter_matches_query(parameter, candidate.query):
                matches.append((parameter, parameter.types.count("X")))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[1], item[0].record.line_start))
    return matches[0][0]


def diagnose_parameter_search(
    requested: tuple[str, ...],
    parameters: list[OffParameter],
    equivalence: dict[str, dict[str, EquivalenceRule]],
    scheme: str,
    step_down_rules: list[StepDownRule],
    bond_orders: Optional[tuple[float, ...]] = None,
    bond_type_rules: Optional[dict[str, BondTypeEquivalenceRule]] = None,
) -> dict[str, str]:
    """Report what the existing OFF search layers find for one missing tuple.

    This is diagnostic only.  It calls the same query construction used by
    ``find_parameter`` and reports evidence from the OFF file; it never
    invents a wildcard, step-down, equivalence, or coefficient.
    """
    exact, equivalence_layers, step_down = _search_query_groups(
        requested,
        equivalence,
        scheme,
        step_down_rules,
        bond_orders=bond_orders,
        bond_type_rules=bond_type_rules,
    )
    equivalence_queries = [item for layer in equivalence_layers for item in layer]
    generic = _dedup_search_queries(exact + equivalence_queries + step_down)
    exact_record = _first_parameter_for_queries(
        parameters, (item for item in exact if item.match_level == "exact"), ignored=False
    )
    symmetry_record = _first_parameter_for_queries(
        parameters, (item for item in exact if item.reversed_order), ignored=False
    )
    equivalence_record = _first_parameter_for_queries(parameters, equivalence_queries, ignored=False)
    step_down_record = _first_parameter_for_queries(parameters, step_down, ignored=False)
    generic_record = _first_generic_parameter(parameters, generic, ignored=False)

    explicit_ignore = (
        _first_parameter_for_queries(parameters, exact, ignored=True)
        or _first_parameter_for_queries(parameters, equivalence_queries, ignored=True)
        or _first_parameter_for_queries(parameters, step_down, ignored=True)
        or _first_generic_parameter(parameters, generic, ignored=True)
    )

    def evidence(parameter: Optional[OffParameter]) -> str:
        return _format_record(parameter) if parameter is not None else "NO"

    return {
        "exact": evidence(exact_record),
        "reverse_symmetry": evidence(symmetry_record),
        "equivalence": evidence(equivalence_record),
        "step_down": evidence(step_down_record),
        "generic": evidence(generic_record),
        "explicit_ignore": evidence(explicit_ignore),
    }

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
