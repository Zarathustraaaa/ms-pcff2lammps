# ms-pcff2lammps 0.1.0b1

First public beta of the audited Materials Studio PCFF to LAMMPS Class-II conversion utility.

## Included

- CAR/MDF topology parsing for Materials Studio-assigned structures;
- PCFF OFF parsing, equivalence handling, explicit wildcard/step-down lookup, and parameter auditing;
- fail-closed handling for unresolved required terms;
- LAMMPS Class-II bonded data generation for the implemented forms;
- fixed-coordinate bonded `run 0` parity checks against a user-supplied local reference;
- a named PAAm pentamer Bend-Bend/AngleAngle validation profile;
- repository hygiene and public synthetic CI that do not require proprietary PCFF data.

## Validation represented in this beta

The aggregate PAAm validation record reports:

- `REQUIRED_MISSING = 0`;
- 40 AngleAngle topologies;
- 99 native exact Bend-Bend components;
- 9 symmetry-resolved components;
- 12 explicitly validated no-op components;
- no unexpected Bend-Bend misses;
- improper/AngleAngle parity on the complete-decomposition checks at approximately `3.8e-12 kcal/mol`;
- relative total-energy RMSE `7.49e-8 kcal/mol`;
- maximum relative total-energy residual `1.11e-7 kcal/mol`.

## Scope

This is a research beta, not a universal PCFF converter. The most complete validation in this release is the PAAm pentamer workflow. New chemistries should be treated as new validation targets.

The release does not redistribute Materials Studio or PCFF parameter databases, native parameter-table exports, or private validation structures. Users must provide legally obtained local inputs.

Production nonbonded setup is outside the scope of this beta. The generated parity input is a fixed-coordinate bonded audit input, not a production MD template.

See `README.md`, `docs/VALIDATION.md`, `docs/LIMITATIONS.md`, and `DISCLAIMER.md` for details.
