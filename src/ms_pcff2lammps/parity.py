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
    *,
    tolerance_kcal_mol: float = PARITY_TOLERANCE_KCAL_MOL,
) -> list[dict[str, object]]:
    """Return like-for-like bonded component comparisons."""
    rows: list[dict[str, object]] = []
    for field in ("ebond", "eangle", "edihed", "eimp"):
        if field not in targets:
            raise ValueError(f"bonded reference is missing required field {field!r}")
        target = float(targets[field])
        value = float(lammps_values[field])
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


def _load_reference_json(path: Path) -> tuple[dict[str, float], str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reference JSON must contain one object")
    targets = {
        field: float(payload[field])
        for field in ("ebond", "eangle", "edihed", "eimp")
        if field in payload
    }
    if len(targets) != 4:
        missing = sorted(set(("ebond", "eangle", "edihed", "eimp")) - set(targets))
        raise ValueError(f"reference JSON is missing fields: {', '.join(missing)}")
    label = str(payload.get("label", path.name))
    tolerance = float(payload.get("tolerance_kcal_mol", PARITY_TOLERANCE_KCAL_MOL))
    if tolerance <= 0.0:
        raise ValueError("reference tolerance must be positive")
    return targets, label, tolerance


def resolve_bonded_reference(args: argparse.Namespace) -> Optional[tuple[dict[str, float], str, float]]:
    profile = getattr(args, "reference_profile", None)
    json_path = getattr(args, "reference_json", None)
    if profile and json_path:
        raise ValueError("choose either --reference-profile or --reference-json, not both")
    if profile:
        record = BONDED_REFERENCE_PROFILES.get(profile)
        if record is None:
            raise ValueError(f"unknown reference profile: {profile}")
        return (
            dict(record["targets"]),
            str(record["label"]),
            float(record["tolerance_kcal_mol"]),
        )
    if json_path:
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
