from __future__ import annotations

from .lammps_writer import *

def parse_lammps_thermo(log_text: str) -> dict[str, float]:
    """Extract the final fixed-coordinate run-0 thermo row.

    The parser is intentionally restricted to the fields emitted by
    ``write_bonded_parity_input``.  It does not infer an energy decomposition
    from total energy or from any other LAMMPS output.
    """
    header: Optional[list[str]] = None
    for raw_line in log_text.splitlines():
        fields = raw_line.split()
        if fields and fields[0] == "Step" and {
            "E_bond", "E_angle", "E_dihed", "E_impro"
        }.issubset(fields):
            header = fields
            continue
        if header is None or not fields or len(fields) != len(header):
            continue
        try:
            values = [float(value.replace("D", "E").replace("d", "e")) for value in fields]
        except ValueError:
            continue
        if values[0] != 0.0:
            continue
        columns = dict(zip(header, values))
        return {
            "ebond": columns["E_bond"],
            "eangle": columns["E_angle"],
            "edihed": columns["E_dihed"],
            "eimp": columns["E_impro"],
        }
    raise ValueError("LAMMPS log has no parseable fixed-coordinate run-0 thermo row")


def bonded_parity_rows(
    lammps_values: dict[str, float],
    targets: dict[str, float],
    tolerance_kcal_mol: float = PARITY_TOLERANCE_KCAL_MOL,
) -> list[dict[str, object]]:
    """Return like-for-like bonded component comparisons."""
    if not math.isfinite(tolerance_kcal_mol) or tolerance_kcal_mol <= 0.0:
        raise ValueError("parity tolerance must be finite and positive")
    rows: list[dict[str, object]] = []
    for field in ("ebond", "eangle", "edihed", "eimp"):
        if field not in targets:
            raise ValueError(f"bonded reference is missing required field {field!r}")
        if field not in lammps_values:
            raise ValueError(f"LAMMPS thermo data is missing required field {field!r}")
        target = float(targets[field])
        value = float(lammps_values[field])
        if not math.isfinite(target) or not math.isfinite(value):
            raise ValueError(f"non-finite bonded energy for {field!r}")
        delta = value - target
        rows.append(
            {
                "field": field,
                "reference": target,
                "lammps": value,
                "delta": delta,
                "pass": abs(delta) < tolerance_kcal_mol,
            }
        )
    return rows


def write_bonded_parity_report(
    path: Path,
    lammps_values: dict[str, float],
    *,
    lammps_log: Path,
    targets: dict[str, float],
    reference_label: str,
    tolerance_kcal_mol: float = PARITY_TOLERANCE_KCAL_MOL,
) -> bool:
    """Write a four-component fixed-geometry bonded parity report."""
    comparisons = bonded_parity_rows(
        lammps_values, targets, tolerance_kcal_mol=tolerance_kcal_mol
    )
    passed = all(bool(row["pass"]) for row in comparisons)
    labels = {
        "ebond": "Bond",
        "eangle": "Angle-group (angle + Class-II stretch couplings)",
        "edihed": "Dihedral-group (torsion + Class-II torsion couplings)",
        "eimp": "Improper-group (inversion + AngleAngle)",
    }
    out = [
        "# PCFF bonded parity",
        "",
        "- Fixed coordinates; `pair_style zero`; `run 0`; no minimization or optimization.",
        f"- Reference: {reference_label}",
        f"- LAMMPS log: `{lammps_log}`",
        f"- Pass criterion: absolute delta < {tolerance_kcal_mol:.6g} kcal/mol.",
        "",
        "| Group | Reference (kcal/mol) | LAMMPS (kcal/mol) | Delta LAMMPS-reference | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in comparisons:
        field = str(row["field"])
        out.append(
            f"| {labels[field]} | {float(row['reference']):.12f} | "
            f"{float(row['lammps']):.12f} | {float(row['delta']):+.12f} | "
            f"{'PASS' if row['pass'] else 'FAIL'} |"
        )
    out.extend(["", f"STATUS: {'PASS' if passed else 'FAIL'}", ""])
    path.write_text("\n".join(out), encoding="utf-8")
    return passed


def _validate_reference_payload(
    payload: dict[str, object], *, source: str
) -> tuple[dict[str, float], float, str]:
    required = ("ebond", "eangle", "edihed", "eimp")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(
            f"bonded reference {source} is missing fields: {', '.join(missing)}"
        )
    try:
        targets = {field: float(payload[field]) for field in required}
        tolerance = float(
            payload.get("tolerance_kcal_mol", PARITY_TOLERANCE_KCAL_MOL)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bonded reference {source} contains non-numeric values"
        ) from exc
    if not all(math.isfinite(value) for value in targets.values()):
        raise ValueError("bonded reference energy targets must be finite")
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("bonded reference tolerance must be finite and positive")
    label = str(payload.get("label", source))
    return targets, tolerance, label


def _load_reference_json(path: Path) -> tuple[dict[str, float], float, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reference JSON must contain one object")
    return _validate_reference_payload(payload, source=str(path))


def resolve_bonded_reference(
    *,
    profile: Optional[str] = None,
    json_path: Optional[Path | str] = None,
) -> Optional[tuple[dict[str, float], float, str]]:
    """Resolve an explicitly selected bonded parity reference.

    No reference is selected implicitly. Keeping this independent of argparse
    makes the reference contract usable from both the CLI and Python API.
    """
    if profile and json_path is not None:
        raise ValueError("choose either --reference-profile or --reference-json, not both")
    if profile:
        record = BONDED_REFERENCE_PROFILES.get(profile)
        if record is None:
            raise ValueError(f"unknown reference profile: {profile}")
        payload: dict[str, object] = dict(record["targets"])
        payload["label"] = record["label"]
        payload["tolerance_kcal_mol"] = record["tolerance_kcal_mol"]
        return _validate_reference_payload(payload, source=profile)
    if json_path is not None:
        path = Path(json_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"reference JSON not found: {path}")
        return _load_reference_json(path)
    return None


def _lammps_executable(requested: Optional[str]) -> Optional[str]:
    if requested:
        candidate = str(Path(requested).expanduser())
        return candidate if Path(candidate).is_file() else None
    return shutil.which("lmp") or shutil.which("lammps")

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
