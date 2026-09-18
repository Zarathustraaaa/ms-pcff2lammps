# Testing and validation model

The project separates **public software tests** from **private scientific integration validation**. This is intentional.

The Materials Studio PCFF database, native parameter-table exports, licensed project files, and the original PAAm validation structures are not distributed with this repository. Their absence from GitHub Actions is not a missing dependency; it is part of the release boundary.

## Public CI

GitHub Actions runs only checks that can be reproduced from the public source tree. The public suite uses synthetic or minimal in-memory fixtures and covers software behavior including:

- OFF parsing and continuation records;
- parameter-match precedence and fail-closed lookup behavior;
- AngleAngle topology construction;
- bonded-only LAMMPS input generation;
- explicit parity-reference handling;
- LAMMPS thermo parsing;
- validation-only CLI guardrails;
- shipped aggregate validation metadata;
- repository hygiene checks that reduce the chance of accidentally committing restricted inputs.

Public CI does **not** require Materials Studio, `pcff.off`, native PCFF exports, LAMMPS, or the author's private molecular examples.

Run the public checks locally with:

```bash
python -m pip install -e '.[dev]'
python -m compileall -q src tests
pytest -q tests
python scripts/check_repository_hygiene.py
ms-pcff2lammps --version
```

## Private integration validation

A complete source-to-LAMMPS parity run requires files that deliberately remain outside the repository. Depending on the workflow, those may include:

- a legally available local PCFF `.off` file;
- matching Materials Studio `.car`/`.mdf` structures with assigned types, charges, bond orders, and connectivity;
- a native Bend-Bend export when exercising the named PAAm mapping profile;
- source-side fixed-geometry energy results or a local reference JSON;
- a compatible LAMMPS executable.

Pass those inputs by local path at runtime. Do not copy them into `tests/`, `examples/`, CI artifacts, issues, or pull requests unless redistribution rights are clear.

For the named PAAm validation profile, the local interface is:

```bash
ms-pcff2lammps generate \
  --car /private/path/PAAm.car \
  --mdf /private/path/PAAm.mdf \
  --off /private/path/pcff.off \
  --native-bendbend /private/path/pcff_native_bendbend.csv \
  --bendbend-profile paam-pentamer-20260917 \
  --forcite-missing-parameters 0 \
  --allow-forcite-cross-zero \
  --reference-json /local/private/paam_bonded_reference.json \
  --lammps /path/to/lmp
```

That command documents the interface only. It is not executed by public CI.

## What to record from private validation

When a change affects parameter matching, coefficient conversion, or topology ordering, record enough information to audit the result without publishing restricted inputs:

- software commit SHA and package version;
- Materials Studio/PCFF version;
- LAMMPS version/build;
- non-sensitive geometry labels;
- `REQUIRED_MISSING` and unexpected-missing counts;
- comparable component residuals;
- total- and relative-energy residuals;
- an explicit note for any source/LAMMPS component pair that is not definitionally comparable.

A missing private fixture should not be turned into a failing public test. Conversely, a public software regression that can be represented synthetically should not be hidden behind a skip simply because the full proprietary validation set is unavailable.
