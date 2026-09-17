# Contributing

Changes should preserve the converter's fail-closed behavior.

Before opening a pull request:

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/check_repository_hygiene.py
```

For changes to parameter matching or coefficient ordering, include a regression test that demonstrates both the accepted case and the failure mode. Do not weaken `REQUIRED_MISSING` behavior to make a new structure pass.

Do not attach or commit proprietary PCFF/Materials Studio parameter databases. Synthetic fixtures are preferred. Aggregate energy values and independently generated minimal examples are acceptable when their redistribution is permitted.

A pull request that changes a validated profile should state:

- the exact topology/parameter rule changed;
- the independent reference used;
- the before/after energy or force residual;
- whether the validation chemistry changed.
