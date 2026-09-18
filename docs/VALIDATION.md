# Validation record

## Validated case

The current high-precision validation case is a fixed-geometry PAAm pentamer assigned with native Materials Studio PCFF 3.1 atom types and charges. The relevant types included `c_1`, `o_1`, `n_2` and `hn2` at the amide groups, together with the PCFF backbone types present in the molecule.

Native Forcite reported zero automatic parameters and zero missing parameters for the reference structure.

## Bonded and Bend-Bend parity

The final corrected audit reported:

- AngleAngle topology count: 40
- native Bend-Bend exact matches: 99
- native symmetry-resolved components: 9
- native Bend-Bend resolved components: 108
- validated Bend-Bend no-op components: 12
- validated Bend-Bend no-op keys: 3
- unexpected missing Bend-Bend components: 0
- `REQUIRED_MISSING`: 0

For the geometries with complete comparable component decompositions:

| Geometry | Component | Forcite | LAMMPS | Delta (LAMMPS - Forcite), kcal/mol |
|---|---|---:|---:|---:|
| BASE | Bond | 6.325101017449614 | 6.325101016477920 | -9.72e-10 |
| BASE | Angle group | 8.806996770480703 | 8.806996770922369 | +4.42e-10 |
| BASE | Dihedral group | -35.840165521689947 | -35.840165521487400 | +2.03e-10 |
| BASE | Improper + AngleAngle | 0.032380110720880 | 0.032380110724667 | +3.79e-12 |
| C1_C9_plus | Bond | 6.325108163688514 | 6.325108162696520 | -9.92e-10 |
| C1_C9_plus | Angle group | 25.037620193381329 | 25.037620193791302 | +4.10e-10 |
| C1_C9_plus | Dihedral group | -35.576764017407278 | -35.576764017200802 | +2.06e-10 |
| C1_C9_plus | Improper + AngleAngle | 0.032380110732577 | 0.032380110736363 | +3.79e-12 |

The corrected component gate intentionally does not compare LAMMPS `eimp` against a Forcite file that contains only `BendBendEnergy`; those quantities are not identical when ordinary inversion is nonzero.

## Total-energy parity

For the four final fixed-coordinate geometries, the absolute total-energy differences were approximately 2.7-2.9e-6 kcal/mol. With BASE as the reference, the relative total-energy statistics were:

- RMSE: `7.4863808e-8 kcal/mol`
- maximum absolute residual: `1.11314449e-7 kcal/mol`
- mean residual: `1.4211935e-8 kcal/mol`

## Nonbonded settings used for this validation

The final nonbonded parity run used:

```text
pair_style lj/class2/coul/cut 12.5
special_bonds lj/coul 0.0 0.0 1.0
```

The Forcite comparison used atom-based electrostatics and van der Waals with a 12.5 Å cutoff and zero spline width. Forcite reported sixth-power combination for diagonal van der Waals parameters.

The current public beta does not generate production nonbonded pair coefficients. Those coefficients were supplied separately in the validation input.

## Interpretation

These results establish implementation parity for the tested structures and settings. They do not establish universal PCFF coverage. New atom types, functional forms, charge models, periodic protocols or production cutoff choices require their own validation.
