# Matching and conversion algorithm

This note documents the behavior implemented in `src/ms_pcff2lammps/converter.py`.

## Topology source

Connectivity comes from the MDF file. The converter does not infer bonds from distance. CAR coordinates and MDF atom records must refer to the same atom names and elements; a mismatch is fatal.

The topology builder generates bonds, angles, proper dihedrals and trigonal inversion records from the explicit connectivity.

## OFF lookup order

For supported sections, the lookup is deliberately ordered from specific to less specific:

1. raw/exact type key;
2. explicit OFF equivalence levels;
3. applicable OFF step-down rules;
4. explicit parameter-side `X` records;
5. explicit `IGNORE` records.

The converter does not create an additional wildcard level that is absent from the OFF file. Bond-order equivalence is parsed independently from atom-type equivalence.

A matched `IGNORE` record is recorded in the audit. A missing diagonal term is never converted to zero.

## Class-II representation conversion

The code translates supported OFF forms to LAMMPS Class-II coefficient ordering. This includes the documented coefficient rearrangements required by the two representations, such as quartic bond/angle polynomial expansion and Class-II torsional cross-term ordering.

The conversion layer operates only after the parameter audit has resolved the relevant source record. It does not fit coefficients.

## Bend-Bend / AngleAngle profile

The current native Bend-Bend implementation is a named validation profile, not a general PCFF theorem.

For `paam-pentamer-20260917`, the validated component ordering is:

- M1: `(J, I, L, K)`
- M2: `(J, L, I, K)`
- M3: `(J, I, L, K)`

The profile also contains one validated symmetry resolution and a three-key no-op allowlist. These rules were selected by cross-geometry identification and verified against independent Forcite energies. They are intentionally unavailable unless the user explicitly selects the profile.

The native Bend-Bend CSV itself is not part of this repository.

## Why the default is fail-closed

During development, a broad interpretation of "Forcite reports zero missing parameters" allowed absent cross terms to be treated as zero. That was useful diagnostically but is unsafe as a generic converter rule because an unresolved lookup can also indicate an incomplete mapping. The public beta therefore requires an explicit opt-in for that behavior.
