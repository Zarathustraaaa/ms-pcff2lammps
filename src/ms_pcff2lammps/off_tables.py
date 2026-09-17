from __future__ import annotations

from .structure import *

def _parameter_layout(section: str, token_count: int) -> Optional[tuple[int, int, int]]:
    """Return (number of types, form index, first value index) for OFF rows."""
    layouts = {
        "BOND_STRETCH": (2, 2, 3),
        "ANGLE_BEND": (3, 3, 4),
        "TORSIONS": (4, 4, 5),
        "INVERSIONS": (4, 4, 5),
        "STRETCH_STRETCH": (3, 3, 4),
        "SEPARATED_STRETCH_STRETCH": (4, 4, 5),
        "STRETCH_BEND_STRETCH": (3, 3, 4),
        "BEND_BEND": (4, 4, 5),
        "STRETCH_TORSION_STRETCH": (4, 4, 5),
        "TORSION_STRETCH": (4, 4, 5),
        "BEND_TORSION_BEND": (4, 4, 5),
        "TORSION_BEND_BEND": (4, 4, 5),
        "DIAGONAL_VDW": (1, 1, 2),
    }
    layout = layouts.get(section)
    if layout and token_count >= layout[2]:
        return layout
    return None


def parse_equivalences(
    sections: list[OffSection], section_name: str
) -> dict[str, dict[str, EquivalenceRule]]:
    """Parse the role-labelled OFF equivalence table without guessing.

    Angle/torsion/inversion tables encode the endpoint rule on a following
    line beginning with ``END``.  Keeping CENTER and END separately is
    important: using the CENTER mapping for every position can select a
    valid-looking but chemically different cross term.
    """
    result: dict[str, dict[str, EquivalenceRule]] = {}
    section = next((item for item in sections if item.name == section_name), None)
    if section is None:
        return result
    current_source: Optional[str] = None
    for record in section.records:
        tokens = record.tokens
        if len(tokens) < 3:
            continue
        if tokens[0] == "END":
            if current_source is None:
                continue
            role = "END"
            # In Materials Studio PCFF, the terminal X is the formal third
            # equivalence level, not merely a row terminator.  It must stay
            # in the parsed path so L3 can be matched against explicit OFF X
            # records.  The raw record remains available for auditing.
            targets = tuple(tokens[1:])
            if targets:
                result.setdefault(current_source, {})[role] = EquivalenceRule(
                    current_source, role, targets, record
                )
            continue
        if len(tokens) < 4:
            continue
        source, role = tokens[0], tokens[1]
        if role not in {"ALL", "CENTER"}:
            continue
        # PCFF equivalence rows encode L1/L2/L3 as the ordered target tokens;
        # the final X is a real formal wildcard level in this file.
        targets = tuple(tokens[2:])
        if not targets:
            continue
        current_source = source
        result.setdefault(source, {})[role] = EquivalenceRule(source, role, targets, record)
    return result


def parse_bond_type_equivalence(
    sections: list[OffSection], section_name: str = "BOND_TYPE_EQUIVALENCE_GENERIC"
) -> dict[str, BondTypeEquivalenceRule]:
    """Parse the formal bond-order equivalence table.

    The PCFF OFF table is a separate two-column table.  It is not an atom
    equivalence table and must not be merged into any of the interaction
    specific ``EQUIVALENCE_*`` sections.
    """
    section = next((item for item in sections if item.name == section_name), None)
    if section is None:
        return {}
    result: dict[str, BondTypeEquivalenceRule] = {}
    for record in section.records:
        if len(record.tokens) < 2:
            continue
        source = record.tokens[0]
        targets = tuple(record.tokens[1:])
        result[source] = BondTypeEquivalenceRule(source, targets, record)
    return result


def bond_order_symbol(order: float) -> str:
    """Convert an MDF numeric bond order to the OFF bond-order symbol."""
    if math.isclose(order, 1.0, rel_tol=0.0, abs_tol=1e-8):
        return "-"
    if math.isclose(order, 1.5, rel_tol=0.0, abs_tol=1e-8):
        return ":"
    if math.isclose(order, 2.0, rel_tol=0.0, abs_tol=1e-8):
        return "="
    if math.isclose(order, 3.0, rel_tol=0.0, abs_tol=1e-8):
        return "#"
    raise ValueError(f"unsupported MDF bond order {order!r}")


def bond_order_levels(
    order: float, rules: dict[str, BondTypeEquivalenceRule]
) -> tuple[str, ...]:
    """Return the formal OFF bond-order path, starting at level 1.

    For the supplied PCFF OFF this produces, for example, ``('-', '~')``
    for a single bond and ``(':', '~')`` for an aromatic bond.  No wildcard
    is added unless the OFF table explicitly supplies it.
    """
    source = bond_order_symbol(order)
    rule = rules.get(source)
    if rule is None:
        return (source,)
    result = [source]
    for target in rule.targets:
        if target not in result:
            result.append(target)
    return tuple(result)


def parse_step_down(sections: list[OffSection], section_name: str) -> list[StepDownRule]:
    """Parse Q1/Q2/Q3 records from a STEP_DOWN section.

    The numeric fields are retained verbatim as a pattern.  They describe the
    OFF hierarchy, not new atom types, so this parser never turns them into a
    guessed parameter.  Equivalence alternatives are tried only after the
    primary mapping, and are labelled ``step-down`` in the audit.
    """
    section = next((item for item in sections if item.name == section_name), None)
    if section is None:
        return []
    result: list[StepDownRule] = []
    for offset, raw in enumerate(section.raw_lines):
        tokens = _tokens(raw)
        level_index = next((idx for idx, token in enumerate(tokens) if re.fullmatch(r"Q[1-9]", token)), None)
        if level_index is None or level_index == 0:
            continue
        try:
            pattern = tuple(int(token) for token in tokens[:level_index])
        except ValueError:
            continue
        result.append(
            StepDownRule(
                section=section_name,
                line_start=section.start_line + offset + 1,
                pattern=pattern,
                level=tokens[level_index],
                raw=raw.strip(),
            )
        )
    return result


def parse_parameters(sections: list[OffSection]) -> dict[str, list[OffParameter]]:
    wanted = {
        "DIAGONAL_VDW",
        "BOND_STRETCH",
        "ANGLE_BEND",
        "TORSIONS",
        "INVERSIONS",
        "STRETCH_STRETCH",
        "SEPARATED_STRETCH_STRETCH",
        "STRETCH_BEND_STRETCH",
        "BEND_BEND",
        "STRETCH_TORSION_STRETCH",
        "TORSION_STRETCH",
        "BEND_TORSION_BEND",
        "TORSION_BEND_BEND",
    }
    parsed: dict[str, list[OffParameter]] = {name: [] for name in wanted}
    for section in sections:
        if section.name not in wanted:
            continue
        for record in section.records:
            layout = _parameter_layout(section.name, len(record.tokens))
            if layout is None:
                continue
            ntypes, form_index, value_index = layout
            form = record.tokens[form_index]
            # The OFF file stores the complete multi-line Fourier row in one
            # logical record.  Some official records append non-numeric
            # metadata such as ``P*`` after the coefficients; those tokens are
            # not coefficient values and must not enter the numerical mapper.
            value_tokens: list[str] = []
            for token in record.tokens[value_index:]:
                if not FLOAT_RE.match(token.replace("D", "E").replace("d", "e")):
                    break
                value_tokens.append(token)
            parsed[section.name].append(
                OffParameter(
                    section=section.name,
                    types=tuple(record.tokens[:ntypes]),
                    form=form,
                    values=tuple(value_tokens),
                    record=record,
                    ignored=form.upper() == "IGNORE",
                )
            )
    return parsed

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
