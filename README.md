# ms-pcff2lammps

`ms-pcff2lammps` is a conservative conversion and audit tool for translating **Materials Studio-assigned PCFF** molecular structures into LAMMPS Class-II bonded topology and coefficients.

The project grew out of a fixed-geometry parity investigation in which a PCFF model assigned by Materials Studio was reproduced in LAMMPS term by term. The public release keeps the useful parts of that workflow—formal OFF lookup, Class-II coefficient conversion, missing-parameter auditing, and fixed-coordinate parity checks—while deliberately avoiding assumptions that were only validated for one system.

> **Status:** `0.1.0b1` is a research beta. The most complete numerical validation currently available is a PAAm pentamer case. Treat other chemistries as new validation targets, not as automatically covered by that result.

## Why this tool exists

PCFF is a Class-II force field. A correct transfer is more involved than copying diagonal bond, angle, torsion, and inversion coefficients. The implementation must also account for force-field equivalence rules, explicit wildcard records, bond-order step-down rules, cross terms, topology ordering, and LAMMPS-specific Class-II conventions.

This tool therefore follows a fail-closed workflow:

1. read the assigned CAR/MDF structure without retyping atoms or guessing bonds;
2. parse the user-supplied OFF database;
3. resolve each required interaction through the explicit OFF hierarchy;
4. write a machine-readable audit trail;
5. stop if a required interaction is unresolved;
6. only then emit LAMMPS Class-II data;
7. optionally run a fixed-coordinate bonded `run 0` parity check against a reference selected by the user.

It does **not** assign PCFF atom types, create charges, redistribute commercial parameter files, or silently invent force-field coefficients.

## Installation

Python 3.10 or newer is required.

```bash
python -m pip install .
ms-pcff2lammps --help
```

For development:

```bash
python -m pip install -e '.[dev]'
pytest -q tests
python scripts/check_repository_hygiene.py
```

The runtime code uses only the Python standard library.

## Inputs

You provide locally:

- a Materials Studio `.car` file;
- the corresponding `.mdf` file containing the assigned atom types, charges, bond orders, and connectivity;
- a legally obtained PCFF `.off` parameter file from your own installation.

The repository intentionally does **not** contain a PCFF parameter database, native parameter-table exports, or the private PAAm structure files used for the full source-side validation. Public CI is therefore self-contained and uses only redistributable synthetic/software fixtures. See [docs/TESTING.md](docs/TESTING.md) and [docs/PARAMETER_DATA.md](docs/PARAMETER_DATA.md).

## Audit first

The default mode is strict:

```bash
ms-pcff2lammps audit \
  --car system.car \
  --mdf system.mdf \
  --off /path/to/pcff.off \
  --outdir audit
```

The main output is `parameter_audit.csv`. The public audit command is fail-closed: missing diagonal terms and unresolved Class-II cross terms remain errors. A source-side statement such as `Missing parameters = 0` is useful provenance, but it does not by itself prove that a local lookup miss is a zero term; the miss may also expose an ordering, equivalence, or parser problem.

The validation-only no-op policy used to reproduce the PAAm reference case is therefore available only from `generate`, behind the named PAAm profile and matching parity safeguards described below. It is not exposed as a generic audit override.

## Generate Class-II bonded data

```bash
ms-pcff2lammps generate \
  --car system.car \
  --mdf system.mdf \
  --off /path/to/pcff.off \
  --outdir converted
```

The generated LAMMPS input is a **fixed-coordinate bonded audit input** using `pair_style zero`. It is not a production MD input and does not attempt to configure production nonbonded electrostatics or van der Waals settings.

If a LAMMPS executable is available:

```bash
ms-pcff2lammps generate \
  --car system.car \
  --mdf system.mdf \
  --off /path/to/pcff.off \
  --outdir converted \
  --lammps /path/to/lmp
```

With no reference selected, the tool runs LAMMPS and reports the bonded thermo components without declaring parity.

## Reference-based parity

A reference is never selected implicitly. You may provide a JSON file:

```json
{
  "label": "fixed-geometry Forcite reference",
  "tolerance_kcal_mol": 0.001,
  "ebond": 1.234,
  "eangle": 2.345,
  "edihed": -0.456,
  "eimp": 0.012
}
```

```bash
ms-pcff2lammps generate \
  --car system.car \
  --mdf system.mdf \
  --off /path/to/pcff.off \
  --reference-json reference.json \
  --lammps /path/to/lmp
```

Only like-for-like bonded groups should be used in such a reference. Materials Studio and LAMMPS do not necessarily expose identical component labels.

## PAAm validation profile

The release includes one named profile, `paam-pentamer-20260917`, for the PAAm pentamer workflow used to establish the current native Bend-Bend/AngleAngle mapping. Reproducing that path additionally requires a **local** native Bend-Bend export from Materials Studio; that export is not distributed here.

```bash
ms-pcff2lammps generate \
  --car PAAm.car \
  --mdf PAAm.mdf \
  --off /path/to/pcff.off \
  --native-bendbend /local/private/pcff_native_bendbend.csv \
  --bendbend-profile paam-pentamer-20260917 \
  --forcite-missing-parameters 0 \
  --allow-forcite-cross-zero \
  --reference-profile paam-pentamer-20260917 \
  --lammps /path/to/lmp
```

The profile is deliberately named and gated. It should not be interpreted as a transferable claim for every PCFF atom type or chemistry.

## Validation record

For the final PAAm fixed-coordinate validation:

| Metric | Result |
|---|---:|
| Required missing parameters | 0 |
| Unexpected Bend-Bend missing components | 0 |
| Native Bend-Bend exact matches | 99 |
| Native symmetry-resolved components | 9 |
| Validated Bend-Bend no-op components | 12 |
| BASE improper + AngleAngle delta | 3.787 × 10⁻¹² kcal/mol |
| C1_C9_plus improper + AngleAngle delta | 3.786 × 10⁻¹² kcal/mol |
| Relative total-energy RMSE | 7.486 × 10⁻⁸ kcal/mol |
| Relative total-energy max residual | 1.113 × 10⁻⁷ kcal/mol |

The associated nonbonded parity run used `pair_style lj/class2/coul/cut 12.5` and `special_bonds lj/coul 0.0 0.0 1.0`. Nonbonded pair coefficients and the direct-cutoff validation were handled separately; `0.1.0b1` intentionally does not generate a production nonbonded input. See [docs/VALIDATION.md](docs/VALIDATION.md) and [docs/NONBONDED.md](docs/NONBONDED.md).

## Current limitations

The limitations are part of the release contract, not footnotes:

- native Bend-Bend support is validated only for the named PAAm profile;
- the built-in atomic mass table currently covers H, C, N, and O;
- production nonbonded setup is outside the scope of this beta;
- some Class-II cross-term applicability logic was developed against the PAAm validation case and requires independent validation on new chemistry;
- a successful parameter audit is not a substitute for energy/force parity on the target system;
- a Forcite `BendBendEnergy` value must not be compared directly with LAMMPS `eimp` when the latter also contains ordinary inversion energy.

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) before applying the converter to a new system.

## Documentation

- [Usage and audit semantics](docs/USAGE.md)
- [Algorithm and lookup order](docs/ALGORITHM.md)
- [Validation record](docs/VALIDATION.md)
- [Testing model: public CI vs private integration validation](docs/TESTING.md)
- [Nonbonded parity notes](docs/NONBONDED.md)
- [Parameter data and licensing](docs/PARAMETER_DATA.md)
- [Provenance](docs/PROVENANCE.md)
- [Limitations](docs/LIMITATIONS.md)
- [Scientific and legal disclaimer](DISCLAIMER.md)

## License and independence

The source code in this repository is released under the BSD 3-Clause License. That license applies only to this project’s code. It does not grant rights to Materials Studio, PCFF parameter databases, or any third-party software or data.

This is independent research software. It is not affiliated with, endorsed by, or sponsored by Dassault Systèmes BIOVIA or the LAMMPS project. Product and project names are used only to describe interoperability.
