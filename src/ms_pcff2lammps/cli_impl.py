from __future__ import annotations

from .commands import *


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ms-pcff2lammps",
        description=(
            "Audit and convert Materials Studio-assigned PCFF bonded/Class-II "
            "terms for LAMMPS. Unresolved required terms fail closed."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="audit current CAR/MDF topology against explicit OFF records")
    audit.add_argument("--car", required=True, help="Materials Studio .car file")
    audit.add_argument("--mdf", required=True, help="Materials Studio .mdf file")
    audit.add_argument("--off", required=True, help="Materials Studio .off file")
    audit.add_argument("--outdir", help="output directory; defaults to OFF directory")
    audit.add_argument("--audit-name", default="parameter_audit.csv")
    audit.add_argument(
        "--forcite-missing-parameters",
        type=int,
        default=None,
        help="assert the native Forcite missing-parameter count for the same structure",
    )
    audit.add_argument(
        "--native-bendbend",
        help="local native PCFF Bend-Bend CSV required by a validated mapping profile",
    )
    audit.add_argument(
        "--bendbend-profile",
        choices=sorted(BEND_BEND_PROFILES),
        help="validated native Bend-Bend mapping profile",
    )
    audit.set_defaults(func=cmd_audit, allow_forcite_cross_zero=False)

    generate = sub.add_parser(
        "generate",
        help="write audited Class-II LAMMPS data/input and optionally run fixed-coordinate run 0",
    )
    generate.add_argument("--car", required=True, help="Materials Studio .car file")
    generate.add_argument("--mdf", required=True, help="Materials Studio .mdf file")
    generate.add_argument("--off", required=True, help="Materials Studio .off file")
    generate.add_argument("--outdir", help="output directory; defaults to OFF directory")
    generate.add_argument("--audit-name", default="parameter_audit.csv")
    generate.add_argument("--data-name", default="pcff_class2.data")
    generate.add_argument("--input-name", default="in.pcff_class2")
    generate.add_argument("--log-name", default="pcff_bonded_parity.log")
    generate.add_argument("--parity-report-name", default="pcff_bonded_parity.md")
    generate.add_argument(
        "--forcite-missing-parameters",
        type=int,
        default=None,
        help="assert the native Forcite missing-parameter count for the same structure",
    )
    generate.add_argument(
        "--allow-forcite-cross-zero",
        action="store_true",
        help=(
            "validation-only PAAm profile: permit the previously validated "
            "Class-II no-op terms; requires the matching profile/reference, "
            "Forcite missing-parameter count 0, and a live LAMMPS parity run"
        ),
    )
    generate.add_argument(
        "--native-bendbend",
        help="local native PCFF Bend-Bend CSV required by a validated mapping profile",
    )
    generate.add_argument(
        "--bendbend-profile",
        choices=sorted(BEND_BEND_PROFILES),
        help="validated native Bend-Bend mapping profile",
    )
    reference = generate.add_mutually_exclusive_group()
    reference.add_argument(
        "--reference-profile",
        choices=sorted(BONDED_REFERENCE_PROFILES),
        help="named fixed-geometry bonded parity reference",
    )
    reference.add_argument(
        "--reference-json",
        help="user-supplied bonded reference JSON with ebond/eangle/edihed/eimp",
    )
    generate.add_argument(
        "--lammps",
        help="LAMMPS executable; if omitted, use lmp/lammps on PATH and otherwise only generate files",
    )
    generate.set_defaults(func=cmd_generate)

    inv = sub.add_parser("inventory", help="inventory OFF sections and preview records")
    inv.add_argument("--off", required=True, help="Materials Studio .off file")
    inv.add_argument("--outdir", help="output directory; defaults to OFF directory")
    inv.add_argument("--preview", type=int, default=3, help="logical records to preview per section")
    inv.add_argument("--json-name", default="pcff_off_inventory.json")
    inv.add_argument("--md-name", default="pcff_off_inventory.md")
    inv.set_defaults(func=cmd_inventory)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
