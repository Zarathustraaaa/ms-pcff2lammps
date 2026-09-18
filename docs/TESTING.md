# Testing and validation

Automated tests are self-contained and use redistributable synthetic fixtures. Materials Studio, PCFF databases, native parameter exports, LAMMPS, and project-specific validation structures are not required for the public test suite.

## Automated tests

The suite covers:

- OFF parsing and continuation records;
- parameter-match precedence and fail-closed lookup behavior;
- AngleAngle topology construction;
- bonded-only LAMMPS input generation;
- explicit parity-reference handling;
- LAMMPS thermo parsing;
- CLI guardrails;
- aggregate validation metadata;
- repository hygiene checks.

Run the checks locally with:

```bash
python -m pip install -e '.[dev]'
python -m compileall -q src tests
pytest -q tests
python scripts/check_repository_hygiene.py
ms-pcff2lammps --version
```

## Local integration validation

A complete source-to-LAMMPS parity run uses local inputs such as:

- a legally available PCFF `.off` file;
- matching Materials Studio `.car`/`.mdf` structures with assigned types, charges, bond orders, and connectivity;
- a native Bend-Bend export when using the named PAAm mapping profile;
- fixed-geometry reference energies;
- a compatible LAMMPS executable.

For the PAAm validation profile:

```bash
ms-pcff2lammps generate \
  --car /path/to/PAAm.car \
  --mdf /path/to/PAAm.mdf \
  --off /path/to/pcff.off \
  --native-bendbend /path/to/pcff_native_bendbend.csv \
  --bendbend-profile paam-pentamer-20260917 \
  --forcite-missing-parameters 0 \
  --allow-forcite-cross-zero \
  --reference-json /path/to/paam_bonded_reference.json \
  --lammps /path/to/lmp
```

Keep third-party parameter data and project-specific structures outside the repository unless redistribution rights are clear. For changes to parameter matching, coefficient conversion, or topology ordering, record the software version, relevant missing-parameter counts, and comparable energy residuals.
