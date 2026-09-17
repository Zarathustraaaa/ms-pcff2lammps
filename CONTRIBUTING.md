# Contributing

Changes should preserve the converter's fail-closed behavior.

Before opening a pull request, run the public self-contained checks:

```bash
python -m pip install -e '.[dev]'
python -m compileall -q src tests
pytest -q tests
python scripts/check_repository_hygiene.py
```

Public CI must remain independent of Materials Studio, licensed PCFF databases, native parameter exports, LAMMPS, and private example structures. If a change requires scientific integration validation, run that check locally with legally available inputs and report only redistributable metadata/results. See `docs/TESTING.md`.

For changes to parameter matching or coefficient ordering, include a regression test that demonstrates both the accepted case and the failure mode. Do not weaken `REQUIRED_MISSING` behavior to make a new structure pass.

Do not attach or commit proprietary PCFF/Materials Studio parameter databases. Synthetic fixtures are preferred. Aggregate energy values and independently generated minimal examples are acceptable when their redistribution is permitted.

A pull request that changes a validated profile should state:

- the exact topology/parameter rule changed;
- the independent reference used;
- the before/after energy or force residual;
- whether the validation chemistry changed.
