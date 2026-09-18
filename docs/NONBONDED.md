# Nonbonded parity notes

The converter's `generate` command currently writes a bonded fixed-coordinate input using `pair_style zero`. This is intentional: the bonded translator can then be checked without coupling the result to a separate nonbonded protocol.

The PAAm validation subsequently used a separate nonbonded `run 0` input with:

```text
units real
atom_style full
boundary f f f
pair_style lj/class2/coul/cut 12.5
special_bonds lj/coul 0.0 0.0 1.0
bond_style class2
angle_style class2
dihedral_style class2
improper_style class2
```

The diagonal 9-6 pair coefficients were supplied separately from the user's local PCFF source. They are not included here.

Two details were important in the validated comparison:

1. the 1-4 nonbonded interactions were retained with `special_bonds lj/coul 0.0 0.0 1.0`;
2. the Forcite reference used zero spline width for the direct-cutoff parity check.

The large nonbonded discrepancy seen before the `special_bonds` correction should not be interpreted as a bonded converter error.

Production MD requires a deliberate choice of boundary conditions, electrostatics, cutoff/spline treatment, pair coefficients and any long-range solver. This repository does not currently generate or certify that production protocol.
