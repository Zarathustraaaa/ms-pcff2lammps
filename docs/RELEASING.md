# Release process

This project separates public software checks from private scientific integration validation. A release is made only when both gates are satisfied for the same source revision.

## 1. Freeze the candidate revision

Choose the exact commit that will be released. Do not change converter logic after private validation without repeating the affected validation.

Record:

- commit SHA;
- package version;
- Python versions used by public CI;
- Materials Studio / PCFF version used for private validation;
- LAMMPS version/build used for the parity run.

## 2. Public release gate

The candidate commit must have a successful `Public CI` run. The workflow covers:

- Python 3.10–3.13 installation and compilation;
- public synthetic/unit tests;
- repository hygiene checks;
- CLI smoke tests;
- source distribution and wheel build;
- `twine check`;
- installation and smoke testing of the built wheel.

The public gate is intentionally independent of Materials Studio, proprietary PCFF data, LAMMPS, and private validation structures.

## 3. Private scientific gate

The exact candidate revision must be installed and exercised against the private validation set with legally available local inputs.

For the current PAAm validation profile this means, at minimum:

- use the current package code, not an older project script;
- use the assigned CAR/MDF structure and the matching local PCFF OFF file;
- use the native Bend-Bend export required by the named profile;
- use the private fixed-geometry reference JSON;
- run the generated LAMMPS fixed-coordinate parity input;
- confirm `REQUIRED_MISSING = 0`;
- confirm there are no unexpected Bend-Bend misses;
- confirm the expected topology/mapping counts for the same fixture;
- compare only definitionally equivalent energy groups.

The current aggregate reference record is stored in
`validation/paam-pentamer-20260917.json`. A release candidate must not weaken
acceptance criteria simply to reproduce that record. Any material deviation
requires investigation before release.

Private validation files remain outside the repository. Record only
redistributable aggregate results, software versions, and the commit SHA.

## 4. Repository hygiene gate

Before tagging:

```bash
python scripts/check_repository_hygiene.py
```

Do not commit or attach:

- PCFF `.off` or `.frc` databases;
- Materials Studio `.car`, `.mdf`, or `.xsd` validation files;
- complete native parameter exports;
- private fixed-geometry reference files;
- personal filesystem paths;
- LAMMPS data/input files that reproduce a third-party force-field table.

## 5. Prepare release metadata

After both gates pass:

1. replace `Unreleased` in `CHANGELOG.md` with the release date;
2. verify the version in `pyproject.toml`, `CITATION.cff`, and
   `src/ms_pcff2lammps/_version.py`;
3. make sure the README still describes the actual validation scope and
   limitations;
4. confirm that the release notes do not imply universal PCFF support.

## 6. Tag and pre-release

For beta versions, create an annotated tag such as:

```bash
git tag -a v0.1.0b1 -m "ms-pcff2lammps 0.1.0b1"
git push origin v0.1.0b1
```

The tag triggers the `Release gate` workflow. That workflow rebuilds and
verifies the package but does not publish to PyPI or any other package index.

Create a GitHub **pre-release** only after the tag workflow is green.

## 7. Release notes

Release notes should state:

- the supported/validated scope;
- that the PCFF parameter database is not redistributed;
- that production nonbonded setup is outside the current beta;
- the aggregate PAAm parity results;
- known limitations;
- the exact commit/tag used.

Do not describe a beta validation profile as universal PCFF support.

## 8. Package-index publication

Publication to PyPI is intentionally outside the current release workflow.
If PyPI publication is added later, use trusted publishing with a protected
GitHub Environment and keep the build/validation gate separate from the
publish job.
