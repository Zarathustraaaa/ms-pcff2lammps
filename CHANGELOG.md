# Changelog

## 0.1.0b1 — 2026-09-18

Initial public beta.

- Added CAR/MDF topology parsing and PCFF OFF inventory/audit tools.
- Added fail-closed diagonal parameter handling.
- Added OFF equivalence, step-down, explicit wildcard and `IGNORE` handling.
- Added LAMMPS Class-II bonded data writer for supported forms.
- Added explicit PAAm pentamer Bend-Bend validation profile.
- Added fixed-coordinate bonded parity reporting with explicit user-supplied reference selection.
- Kept private validation reference energies outside the public package.
- Disabled implicit PAAm parity references for general conversions.
- Disabled implicit cross-term zeroing; the legacy Forcite-backed policy now requires an explicit opt-in.
- Documented the validated nonbonded parity settings without redistributing PCFF parameter data.
