# Provenance

The public beta is derived from the validated `ms_pcff_lammps.py` converter used in the 2026-09-17 PAAm parity work.

Source snapshot SHA-256:

```text
9f30964ea5d7b108f8362e4bf2666a87cf7442061d63ddb32f791787fe3c8b20  ms_pcff_lammps.py
```

Corrected final parity report SHA-256:

```text
c545b23cebe76694638ecc145ca30c3932343a3bb6e51b02f63c2f07e66ab739  final_pcff_parity_report_corrected.txt
```

The packaged interface differs from the original project script in several ways:

- parity references are supplied through `--reference-json` rather than embedded;
- missing Class-II cross terms fail closed unless the explicit validation-only override is used with a zero native missing-parameter count;
- native Bend-Bend conversion requires the `paam-pentamer-20260917` profile;
- generic output filenames replace PAAm-specific defaults;
- a package/console entry point and automated tests are included.

The validated coefficient transformations and PAAm Bend-Bend mapping used by the named profile were preserved.

Git tags and commit hashes are the canonical identifiers for package revisions.

Automated tests use redistributable fixtures. Full parity validation depends on local, appropriately licensed inputs and is represented in the repository by aggregate validation metadata.
