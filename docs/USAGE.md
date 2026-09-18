# Usage and audit semantics

## Commands

`audit` resolves the interactions implied by CAR/MDF connectivity against the supplied OFF database and writes `parameter_audit.csv`.

`generate` performs the same audit and, only if no required term is unresolved, writes a Class-II LAMMPS data file and a fixed-coordinate bonded input.

`inventory` is a read-only diagnostic command for inspecting OFF sections and logical records. Development-only trace/classification utilities are intentionally not exposed in the public beta CLI.

## Exit behavior

The converter is intended for scripts and CI pipelines. A required parameter miss returns a non-zero exit code. A LAMMPS failure or a selected parity reference outside tolerance also returns non-zero.

## Cross-term zero policy

By default, every unresolved Class-II cross term is `REQUIRED_MISSING`.

The optional pair

```text
--forcite-missing-parameters 0
--allow-forcite-cross-zero
```

allows an unresolved Class-II cross term to be recorded as a validation-backed no-op. The pair is accepted only when both options are present. It exists to reproduce a separately audited native Forcite structure; it is not a general PCFF rule.

The audit records the origin of every such zero in the `zero_source` field.

## Native Bend-Bend profile

`--native-bendbend` requires a named `--bendbend-profile`. In `0.1.0b1` the only profile is `paam-pentamer-20260917`.

This gate is intentional. The profile contains a sequence ordering and a three-key no-op allowlist established from the PAAm validation set. Applying those rules silently to arbitrary PCFF chemistry would overstate the evidence.

## Fixed-coordinate LAMMPS input

The generated audit input uses:

```text
units real
atom_style full
boundary f f f
pair_style zero 1.0
bond_style class2
angle_style class2
dihedral_style class2
improper_style class2
run 0
```

This isolates the bonded/Class-II conversion. It is not a production MD template.

## Reference parity

A parity check is performed only when `--reference-json` is given. With neither option, the LAMMPS run is reported without a PASS/FAIL scientific claim.

A reference JSON must provide `ebond`, `eangle`, `edihed`, and `eimp`. The values must correspond to the same grouping as the generated LAMMPS bonded audit. Do not compare an isolated source subcomponent to a LAMMPS thermo field that contains additional terms.
