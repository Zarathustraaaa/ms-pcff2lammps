# Limitations

This file is part of the release contract. A limitation listed here should be treated as unsupported behavior unless a later release explicitly changes it.

## Validation scope

The only full high-precision chemistry validation bundled with `0.1.0b1` is the named PAAm pentamer workflow. The parser and several Class-II transformations are more general, but broader chemistry coverage has not been demonstrated by the current repository.

## Native Bend-Bend profile

The native Bend-Bend mapping is enabled only through `paam-pentamer-20260917`. It contains PAAm-specific validated ordering, symmetry and no-op decisions. Do not apply that profile to unrelated systems simply because the same PCFF force-field name is used.

## Elements

The current built-in mass table covers H, C, N and O. Other elements fail explicitly rather than receiving a guessed mass.

## Nonbonded production inputs

The data writer does not currently embed or generate a complete production nonbonded setup. The `generate` subcommand writes a bonded `run 0` input with `pair_style zero`.

## Periodicity and boxes

The fixed-coordinate data writer is primarily a parity tool. Users must review boundary conditions and box construction before production simulation.

## Force validation

The bundled release record is an energy parity validation. A new production system should also be checked for force consistency when the intended use depends on forces or dynamics.

## Forcite component naming

Forcite and LAMMPS do not necessarily aggregate energy terms under the same names. Comparisons are valid only when the definitions are known to match. The corrected PAAm gate explicitly excludes non-comparable Bend-Bend-only versus `eimp` rows.

## Automatic and missing parameters

The tool does not reproduce proprietary internal Forcite automatic-parameter behavior. Unresolved required terms are a stop condition. The optional cross-zero path is a validation aid, not a generic automatic-parameter substitute.
