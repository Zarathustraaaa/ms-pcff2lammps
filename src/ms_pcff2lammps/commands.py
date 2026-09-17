from __future__ import annotations

from .parity import *

def cmd_generate(args: argparse.Namespace) -> int:
    car = Path(args.car).expanduser().resolve()
    mdf = Path(args.mdf).expanduser().resolve()
    off = Path(args.off).expanduser().resolve()
    native_path = (
        Path(args.native_bendbend).expanduser().resolve()
        if args.native_bendbend
        else None
    )
    input_paths = (car, mdf, off) + ((native_path,) if native_path is not None else ())
    for path in input_paths:
        if not path.is_file():
            print(f"ERROR: input file not found: {path}", file=sys.stderr)
            return 2
    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else off.parent
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        reference = resolve_bonded_reference(args)
        system = parse_molecular_system(car, mdf)
        sections = parse_off(off)
        native_records = (
            native_bendbend_records(native_path)
            if native_path is not None
            else None
        )
        rows = audit_system(
            system,
            sections,
            forcite_missing_parameters=args.forcite_missing_parameters,
            allow_forcite_cross_zero=args.allow_forcite_cross_zero,
            native_bendbend=native_records,
            bendbend_profile=args.bendbend_profile,
        )
        parameters = parse_parameters(sections)
        if native_records is not None:
            parameters = add_native_bendbend_parameters(parameters, native_records)
        audit_path = outdir / args.audit_name
        write_audit(audit_path, rows)
        required = sum(1 for row in rows if row.status == REQUIRED_MISSING)
        if required:
            print(f"REQUIRED_MISSING: {required}")
            print(f"Wrote: {audit_path}")
            print("Refusing to generate LAMMPS data/input.")
            return 1
        data_path = outdir / args.data_name
        input_path = outdir / args.input_name
        write_lammps_class2_data(data_path, system, rows, parameters)
        write_bonded_parity_input(input_path, data_path.name)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    counts = {status: sum(1 for row in rows if row.status == status) for status in (
        "MATCHED", "OFF_IGNORE", CLASS2_CROSS_ZERO, REQUIRED_MISSING
    )}
    print(f"REQUIRED_MISSING: {counts[REQUIRED_MISSING]}")
    print(f"MATCHED: {counts['MATCHED']}")
    print(f"OFF_IGNORE: {counts['OFF_IGNORE']}")
    print(f"CLASS2_CROSS_ZERO: {counts[CLASS2_CROSS_ZERO]}")
    if native_records is not None:
        native_rows = [row for row in rows if row.interaction == "AngleAngle"]
        print(f"AngleAngle topology count: {len(native_rows) // 3}")
        print(
            "native Bend-Bend matched count: "
            f"{sum(row.status == 'MATCHED' for row in native_rows)}"
        )
        print(
            "native symmetry-resolved count: "
            f"{sum(row.match_level == 'NATIVE_BENDBEND_SYMMETRY' for row in native_rows)}"
        )
        print(
            "validated noop count: "
            f"{sum(row.match_level == 'NATIVE_BENDBEND_NOOP' for row in native_rows)}"
        )
        print(
            "unexpected missing count: "
            f"{sum(row.match_level == 'NATIVE_BENDBEND_UNEXPECTED_MISSING' for row in native_rows)}"
        )
    print(f"Wrote: {audit_path}")
    print(f"Wrote: {data_path}")
    print(f"Wrote: {input_path}")

    executable = _lammps_executable(args.lammps)
    if executable is None:
        print("LAMMPS: not run (no local executable; use --lammps /path/to/lmp)")
        return 0
    run = subprocess.run(
        [executable, "-in", str(input_path)],
        cwd=outdir,
        capture_output=True,
        text=True,
        check=False,
    )
    log_path = outdir / args.log_name
    log_path.write_text(
        "--- stdout ---\n" + run.stdout + "\n--- stderr ---\n" + run.stderr,
        encoding="utf-8",
    )
    print(f"LAMMPS exit code: {run.returncode}")
    print(f"Wrote: {log_path}")
    if run.returncode:
        print("STATUS: LAMMPS_RUN_FAILED")
        return 1
    try:
        lammps_values = parse_lammps_thermo(run.stdout + "\n" + run.stderr)
    except ValueError as exc:
        print(f"ERROR: cannot parse fixed-coordinate LAMMPS thermo output: {exc}", file=sys.stderr)
        return 1

    if reference is None:
        print("Bonded thermo (no reference selected):")
        for field in ("ebond", "eangle", "edihed", "eimp"):
            print(f"  {field}: {lammps_values[field]:.12f}")
        print("STATUS: LAMMPS_RUN_COMPLETE_NO_REFERENCE")
        return 0

    targets, reference_label, tolerance = reference
    parity_path = outdir / args.parity_report_name
    try:
        parity_pass = write_bonded_parity_report(
            parity_path,
            lammps_values,
            lammps_log=log_path,
            targets=targets,
            reference_label=reference_label,
            tolerance_kcal_mol=tolerance,
        )
    except (ValueError, OSError) as exc:
        print(f"ERROR: cannot produce bonded parity report: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote: {parity_path}")
    for row in bonded_parity_rows(lammps_values, targets, tolerance_kcal_mol=tolerance):
        print(
            f"{row['field']}: reference={float(row['reference']):.12f} "
            f"LAMMPS={float(row['lammps']):.12f} delta={float(row['delta']):+.12f}"
        )
    if not parity_pass:
        print("STATUS: PCFF_BONDED_PARITY_FAIL")
        return 1
    print("STATUS: PCFF_BONDED_PARITY_PASS")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    car = Path(args.car).expanduser().resolve()
    mdf = Path(args.mdf).expanduser().resolve()
    off = Path(args.off).expanduser().resolve()
    for path in (car, mdf, off):
        if not path.is_file():
            print(f"ERROR: input file not found: {path}", file=sys.stderr)
            return 2
    try:
        system = parse_molecular_system(car, mdf)
        sections = parse_off(off)
        native_records = (
            native_bendbend_records(Path(args.native_bendbend).expanduser().resolve())
            if args.native_bendbend
            else None
        )
        rows = audit_system(
            system,
            sections,
            forcite_missing_parameters=args.forcite_missing_parameters,
            allow_forcite_cross_zero=args.allow_forcite_cross_zero,
            native_bendbend=native_records,
            bendbend_profile=args.bendbend_profile,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else off.parent
    outdir.mkdir(parents=True, exist_ok=True)
    audit_path = outdir / args.audit_name
    write_audit(audit_path, rows)

    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row.interaction, {}).setdefault(row.status, 0)
        counts[row.interaction][row.status] += 1
    missing = sum(1 for row in rows if row.status == REQUIRED_MISSING)
    cross_zero = sum(1 for row in rows if row.status == CLASS2_CROSS_ZERO)
    print(f"CAR/MDF atoms: {len(system.atoms)}")
    print(f"CAR/MDF bonds: {len(system.bonds)}")
    print(f"Angles: {len(molecular_interactions(system)['angle'])}")
    print(f"Dihedrals: {len(molecular_interactions(system)['dihedral'])}")
    print(f"Impropers: {len(molecular_interactions(system)['improper'])}")
    print("Audit summary:")
    for interaction, status_counts in counts.items():
        matched = status_counts.get("MATCHED", 0)
        ignored = status_counts.get("OFF_IGNORE", 0)
        missing_count = status_counts.get(REQUIRED_MISSING, 0)
        interaction_cross_zero = status_counts.get(CLASS2_CROSS_ZERO, 0)
        print(
            f"  {interaction:<20} matched={matched:>4} ignored={ignored:>4} "
            f"cross_zero={interaction_cross_zero:>4} required_missing={missing_count:>4}"
        )
    bond_type_rules = parse_bond_type_equivalence(sections)
    print("OFF bond-order equivalence:")
    for symbol in ("-", ":", "=", "#", "~"):
        rule = bond_type_rules.get(symbol)
        targets = " ".join(rule.targets) if rule is not None else "NO RULE"
        print(f"  {symbol} -> {targets}")
    print("OFF step-down rules:")
    for section_name in sorted(set(SECTION_STEP_DOWN.values())):
        rule_count = len(parse_step_down(sections, section_name))
        if rule_count:
            print(f"  {section_name}: {rule_count} pattern(s)")
    level_counts = {
        "Exact": sum(1 for row in rows if row.match_level in {"exact", "symmetry"}),
        "Equivalence level 1": sum(1 for row in rows if row.match_level == "equivalence-level-1"),
        "Equivalence level 2": sum(1 for row in rows if row.match_level == "equivalence-level-2"),
        "Equivalence level 3": sum(1 for row in rows if row.match_level == "equivalence-level-3"),
        "Step-down": sum(1 for row in rows if row.match_level.startswith("step-down")),
        "OFF_IGNORE": sum(1 for row in rows if row.status == "OFF_IGNORE"),
        REQUIRED_MISSING: missing,
        CLASS2_CROSS_ZERO: cross_zero,
    }
    print("Final classification:")
    for label, count in level_counts.items():
        print(f"  {label:<13} {count}")
    print(f"Wrote: {audit_path}")
    if missing:
        print(f"STRICT STOP: {missing} required interaction records are missing; no LAMMPS data/input generated.")
        return 1
    print("All required interaction records matched explicitly; conversion stage may proceed.")
    return 0


def _preview_record(record: OffRecord) -> str:
    return "\n".join(record.raw_lines).strip()


def inventory(path: Path, preview: int) -> dict:
    sections = parse_off(path)
    result = {
        "file": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sections": [],
    }
    for section in sections:
        result["sections"].append(
            {
                "name": section.name,
                "start_line": section.start_line,
                "end_line": section.end_line,
                "record_count": len(section.records),
                "nonempty_data_lines": sum(bool(_clean_line(x)) and _clean_line(x) != "END" for x in section.raw_lines),
                "preview": [
                    {
                        "line_start": record.line_start,
                        "tokens": record.tokens,
                        "raw": _preview_record(record),
                    }
                    for record in section.records[:preview]
                ],
            }
        )
    return result


def render_inventory_markdown(report: dict) -> str:
    out: list[str] = []
    out.append("# Materials Studio PCFF OFF inventory")
    out.append("")
    out.append(f"- File: `{report['file']}`")
    out.append(f"- Bytes: {report['bytes']}")
    out.append(f"- Sections: {len(report['sections'])}")
    out.append("")
    out.append("| # | Section | Lines | Logical records | Data lines |")
    out.append("|---:|---|---:|---:|---:|")
    for idx, section in enumerate(report["sections"], 1):
        out.append(
            f"| {idx} | `{section['name']}` | {section['start_line']}–{section['end_line']} | "
            f"{section['record_count']} | {section['nonempty_data_lines']} |"
        )
    out.append("")
    out.append("## Record previews")
    out.append("")
    for section in report["sections"]:
        out.append(f"### `{section['name']}`")
        out.append("")
        if not section["preview"]:
            out.append("(no data records)")
            out.append("")
            continue
        out.append("```text")
        for record in section["preview"]:
            out.append(f"line {record['line_start']}: {record['raw']}")
        out.append("```")
        out.append("")
    return "\n".join(out)


def cmd_inventory(args: argparse.Namespace) -> int:
    off = Path(args.off).expanduser().resolve()
    if not off.is_file():
        print(f"ERROR: OFF file not found: {off}", file=sys.stderr)
        return 2
    report = inventory(off, args.preview)
    outdir = Path(args.outdir).expanduser().resolve() if args.outdir else off.parent
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / args.json_name
    md_path = outdir / args.md_name
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_inventory_markdown(report), encoding="utf-8")
    print(f"OFF: {off}")
    print(f"Sections: {len(report['sections'])}")
    for idx, section in enumerate(report["sections"], 1):
        print(f"{idx:02d} {section['name']:<34} records={section['record_count']:>5} lines={section['nonempty_data_lines']:>5}")
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    return 0

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
