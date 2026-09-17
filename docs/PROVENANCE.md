# Provenance and release preparation

The public beta was prepared from the validated project script `ms_pcff_lammps.py` used in the 2026-09-17 PAAm parity work.

Source snapshot SHA-256:

```text
9f30964ea5d7b108f8362e4bf2666a87cf7442061d63ddb32f791787fe3c8b20  ms_pcff_lammps.py
```

Corrected final parity report SHA-256:

```text
c545b23cebe76694638ecc145ca30c3932343a3bb6e51b02f63c2f07e66ab739  final_pcff_parity_report_corrected.txt
```

The public package intentionally changes several interface defaults relative to that working script:

- implicit PAAm reference energies were replaced by explicit `--reference-profile` / `--reference-json` selection;
- the broad Forcite-backed missing-cross-term-to-zero behavior was changed to fail closed unless `--allow-forcite-cross-zero` is supplied together with a zero native missing-parameter count;
- native Bend-Bend conversion now requires the explicit `paam-pentamer-20260917` profile;
- generic output filenames replace PAAm-specific defaults;
- a package/console entry point and repository tests were added.

The validated coefficient transformations and the PAAm Bend-Bend mapping used by the named profile were not re-fit during repository preparation.

Public-package converter SHA-256 at release preparation:

```text
c7075e1d3e387052ee011fab7e271edac0f2956b4c5332619a746ce04936cb38  src/ms_pcff2lammps/converter.py
```

This checksum will naturally change when the source changes; Git tags and commit hashes are the canonical identifiers after publication.

## Public CI versus source-side validation

GitHub Actions is intentionally limited to redistributable software/synthetic fixtures. The PCFF database, native parameter exports, and private PAAm structure files used for the scientific parity exercise are external validation inputs, not repository dependencies. Their absence from public CI is by design; the numerical validation record is retained as aggregate metadata and is only reproduced locally with appropriately licensed inputs.

