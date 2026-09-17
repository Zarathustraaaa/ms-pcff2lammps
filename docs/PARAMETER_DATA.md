# Parameter data and licensing

This repository contains conversion code, tests built from synthetic data, and aggregate validation results. It intentionally does not contain:

- `pcff.off`;
- `pcff.frc` copied from a third-party installation;
- a full native PCFF Bend-Bend parameter export;
- Materials Studio project files or assigned structures from the validation run;
- LAMMPS data/input files containing a redistributed PCFF parameter table.

Users must point the tool at their own local files.

The CI workflow runs `scripts/check_repository_hygiene.py` to reduce the chance of accidentally committing common Materials Studio or raw parameter assets.

If you contribute a test case, prefer a small synthetic parameter file whose values were authored specifically for the test. Do not submit proprietary force-field tables in issues, pull requests or fixtures.
