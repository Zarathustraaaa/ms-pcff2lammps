from __future__ import annotations

from .off_tables import *

def _format_record(parameter: Optional[OffParameter]) -> str:
    if parameter is None:
        return ""
    preview = "\n".join(parameter.record.raw_lines).strip()
    return f"{parameter.section}:line {parameter.record.line_start}: {preview}"


def _roles_for_scheme(scheme: str, arity: int, position: int) -> str:
    if scheme in {"all", "bond"}:
        return "ALL"
    if scheme == "angle":
        return "CENTER" if position == 1 else "END"
    if scheme == "torsion":
        return "CENTER" if position in {1, 2} else "END"
    if scheme == "inversion":
        return "CENTER" if position == 0 else "END"
    raise ValueError(f"unknown OFF equivalence scheme: {scheme}")


def _formal_equivalence_paths(
    requested: tuple[str, ...],
    equivalence: dict[str, dict[str, EquivalenceRule]],
    scheme: str,
) -> list[tuple[str, ...]]:
    """Return the OFF-defined L1/L2/L3 path for each tuple position.

    This PCFF file uses the first target token as L1 (specific), the next
    target as L2 (lower equivalence), and the explicit final ``X`` as L3.
    When a type has no applicable equivalence row, its own type is the only
    formal L1 candidate.  No level beyond L3 is created.
    """
    paths: list[tuple[str, ...]] = []
    for position, source in enumerate(requested):
        role = _roles_for_scheme(scheme, len(requested), position)
        rule = equivalence.get(source, {}).get(role) or equivalence.get(source, {}).get("ALL")
        if rule is None or not rule.targets:
            paths.append((source,))
        else:
            paths.append(rule.targets[:3])
    return paths


def _symmetry_forms(
    types: tuple[str, ...], atom_levels: tuple[int, ...], symmetry: str
) -> list[tuple[tuple[str, ...], tuple[int, ...], bool]]:
    result = [(types, atom_levels, False)]
    if symmetry == "outer" and len(types) == 4:
        for outer in itertools.permutations(range(1, 4)):
            candidate = (types[0],) + tuple(types[index] for index in outer)
            candidate_levels = (atom_levels[0],) + tuple(atom_levels[index] for index in outer)
            if candidate != types:
                result.append((candidate, candidate_levels, False))
    else:
        reverse = tuple(reversed(types))
        reverse_levels = tuple(reversed(atom_levels))
        if reverse != types:
            result.append((reverse, reverse_levels, True))
    return result


def _dedup_search_queries(queries: Iterable[SearchQuery]) -> list[SearchQuery]:
    seen: set[tuple[str, ...]] = set()
    result: list[SearchQuery] = []
    for candidate in queries:
        if candidate.query in seen:
            continue
        seen.add(candidate.query)
        result.append(candidate)
    return result


def _candidate_forms(
    types: tuple[str, ...],
    atom_levels: tuple[int, ...],
    match_level: str,
    symmetry: str,
    bond_levels: tuple[int, ...] = (),
) -> list[SearchQuery]:
    return [
        SearchQuery(query, match_level, reversed_order, levels, bond_levels)
        for query, levels, reversed_order in _symmetry_forms(types, atom_levels, symmetry)
    ]


def _evaluate_step_down_rule(
    requested: tuple[str, ...],
    paths: list[tuple[str, ...]],
    symmetry: str,
    rule: StepDownRule,
    bond_orders: Optional[tuple[float, ...]],
    bond_type_rules: dict[str, BondTypeEquivalenceRule],

) -> StepDownEvaluation:
    """Evaluate one explicit OFF STEP_DOWN rank vector.

    A step-down pattern is encoded as all atom-equivalence ranks followed by
    all bond-order-equivalence ranks.  This is the PCFF OFF convention used
    by the public Materials Studio example.  A rank is 1-based in the OFF
    file; rank 1 is the first formal equivalence alternative, not the raw MS
    type.  Raw types are handled by the exact layer.
    """
    arity = len(requested)
    expected_length = 2 * arity - 1
    if len(rule.pattern) != expected_length:
        return StepDownEvaluation(
            rule,
            False,
            f"pattern length {len(rule.pattern)} does not match unary/topology arity {arity} "
            f"(expected {expected_length})",
        )

    atom_ranks = rule.pattern[:arity]
    bond_ranks = rule.pattern[arity:]
    for position, rank in enumerate(atom_ranks):
        if rank < 1 or rank > len(paths[position]):
            return StepDownEvaluation(
                rule,
                False,
                f"atom position {position + 1} requests rank {rank}, but the formal "
                f"equivalence path has ranks 1..{len(paths[position])}",
            )

    if bond_orders is None:
        if bond_ranks:
            return StepDownEvaluation(
                rule,
                False,
                "bond-order ranks present but no MDF bond orders were supplied",
            )
    else:
        if len(bond_orders) != len(bond_ranks):
            return StepDownEvaluation(
                rule,
                False,
                f"MDF supplied {len(bond_orders)} bond order(s), OFF pattern requires "
                f"{len(bond_ranks)}",
            )
        for bond_index, (order, rank) in enumerate(zip(bond_orders, bond_ranks), 1):
            order_path = bond_order_levels(order, bond_type_rules)
            if rank < 1 or rank > len(order_path):
                return StepDownEvaluation(
                    rule,
                    False,
                    f"bond position {bond_index} requests rank {rank}, but MDF order "
                    f"{order:g} has OFF path {' -> '.join(order_path)}",
                )

    query = tuple(paths[position][rank - 1] for position, rank in enumerate(atom_ranks))
    candidates = tuple(
        _candidate_forms(
            query,
            atom_ranks,
            f"step-down-{rule.level}",
            symmetry,
            bond_ranks,
        )
    )
    return StepDownEvaluation(rule, True, "candidate generated from explicit OFF rule", query, candidates)


def _step_down_candidates(
    requested: tuple[str, ...],
    paths: list[tuple[str, ...]],
    symmetry: str,
    step_down_rules: list[StepDownRule],
    bond_orders: Optional[tuple[float, ...]],
    bond_type_rules: dict[str, BondTypeEquivalenceRule],
) -> list[SearchQuery]:
    """Materialize only rank vectors explicitly present and applicable in OFF."""
    result: list[SearchQuery] = []
    for rule in sorted(step_down_rules, key=lambda item: item.line_start):
        evaluation = _evaluate_step_down_rule(
            requested,
            paths,
            symmetry,
            rule,
            bond_orders,
            bond_type_rules,
        )
        if evaluation.applicable:
            result.extend(evaluation.candidates)
    return _dedup_search_queries(result)


def _search_query_groups(
    requested: tuple[str, ...],
    equivalence: dict[str, dict[str, EquivalenceRule]],
    scheme: str,
    step_down_rules: list[StepDownRule],
    bond_orders: Optional[tuple[float, ...]] = None,
    bond_type_rules: Optional[dict[str, BondTypeEquivalenceRule]] = None,
) -> tuple[list[SearchQuery], list[list[SearchQuery]], list[SearchQuery]]:
    """Build exact, formal equivalence-level, and explicit step-down layers."""
    symmetry = "outer" if scheme == "inversion" else "reverse"
    paths = _formal_equivalence_paths(requested, equivalence, scheme)
    exact_queries = _candidate_forms(requested, (0,) * len(requested), "exact", symmetry)

    # Each equivalence level is uniform across the interaction tuple.  Mixed
    # rank vectors are not inferred here; they are admitted only by a
    # matching STEP_DOWN record below.
    equivalence_layers: list[list[SearchQuery]] = []
    max_level = min(3, max((len(path) for path in paths), default=0))
    for level in range(1, max_level + 1):
        if not all(len(path) >= level for path in paths):
            continue
        query = tuple(path[level - 1] for path in paths)
        equivalence_layers.append(
            _dedup_search_queries(
                _candidate_forms(
                    query,
                    (level,) * len(requested),
                    f"equivalence-level-{level}",
                    symmetry,
                )
            )
        )

    step_queries = _step_down_candidates(
        requested,
        paths,
        symmetry,
        step_down_rules,
        bond_orders,
        bond_type_rules or {},
    )
    return exact_queries, equivalence_layers, step_queries


def _parameter_matches_query(parameter: OffParameter, query: tuple[str, ...]) -> bool:
    """Match an OFF parameter record, honoring only explicit parameter X."""
    return len(parameter.types) == len(query) and all(
        pattern == "X" or pattern == actual
        for pattern, actual in zip(parameter.types, query)
    )


def find_parameter(
    requested: tuple[str, ...],
    parameters: list[OffParameter],
    equivalence: dict[str, dict[str, EquivalenceRule]],
    scheme: str,
    step_down_rules: list[StepDownRule],
    bond_orders: Optional[tuple[float, ...]] = None,
    bond_type_rules: Optional[dict[str, BondTypeEquivalenceRule]] = None,
) -> tuple[Optional[OffParameter], str, bool]:
    """Find an explicit OFF record using the formal hierarchy only."""
    by_types: dict[tuple[str, ...], list[OffParameter]] = {}
    for parameter in parameters:
        by_types.setdefault(parameter.types, []).append(parameter)
    exact_queries, equivalence_layers, step_queries = _search_query_groups(
        requested,
        equivalence,
        scheme,
        step_down_rules,
        bond_orders=bond_orders,
        bond_type_rules=bond_type_rules,
    )
    normal_queries = _dedup_search_queries(
        list(exact_queries) + [item for layer in equivalence_layers for item in layer] + step_queries
    )

    def exact_lookup(ignored: bool) -> tuple[Optional[OffParameter], Optional[SearchQuery]]:
        for candidate in normal_queries:
            for parameter in by_types.get(candidate.query, []):
                if parameter.ignored == ignored:
                    return parameter, candidate
        return None, None

    parameter, candidate = exact_lookup(ignored=False)
    if parameter is not None and candidate is not None:
        return parameter, candidate.match_level, candidate.reversed_order

    # Parameter-side X is an explicit OFF record feature.  It is searched
    # only after every concrete exact/equivalence/step-down query, so a broad
    # X record cannot mask a more specific concrete parameter.
    wildcard_matches: list[tuple[int, int, OffParameter, SearchQuery]] = []
    for candidate in normal_queries:
        for parameter in parameters:
            if parameter.ignored or "X" not in parameter.types:
                continue
            if _parameter_matches_query(parameter, candidate.query):
                wildcard_matches.append(
                    (parameter.types.count("X"), parameter.record.line_start, parameter, candidate)
                )
    if wildcard_matches:
        _, _, parameter, candidate = min(wildcard_matches, key=lambda item: (item[0], item[1]))
        return parameter, candidate.match_level, candidate.reversed_order

    # IGNORE is accepted only after all non-IGNORE concrete and explicit-X
    # records were exhausted.
    parameter, candidate = exact_lookup(ignored=True)
    if parameter is not None and candidate is not None:
        return parameter, f"IGNORE:{candidate.match_level}", candidate.reversed_order
    ignore_matches: list[tuple[int, int, OffParameter, SearchQuery]] = []
    for candidate in normal_queries:
        for parameter in parameters:
            if not parameter.ignored or "X" not in parameter.types:
                continue
            if _parameter_matches_query(parameter, candidate.query):
                ignore_matches.append(
                    (parameter.types.count("X"), parameter.record.line_start, parameter, candidate)
                )
    if ignore_matches:
        _, _, parameter, candidate = min(ignore_matches, key=lambda item: (item[0], item[1]))
        return parameter, f"IGNORE:{candidate.match_level}", candidate.reversed_order
    return None, "", False

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
