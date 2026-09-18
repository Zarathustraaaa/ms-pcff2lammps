# Parameter data and licensing

This repository contains conversion code, synthetic software tests, and aggregate validation metadata. It intentionally does not contain Materials Studio or third-party PCFF parameter databases, native parameter-table exports, or the private structures used for the source-side validation.

Files that must remain local include, in particular:

- PCFF `.off` / `.frc` databases obtained from third-party software;
- Materials Studio `.car`, `.mdf`, and `.xsd` project or assigned-structure files from private validation work;
- complete native Bend-Bend or other force-field table exports;
- LAMMPS inputs or data files that reproduce a third-party parameter database rather than a small independently authored synthetic fixture;
- source-side reports that disclose restricted project contents or personal filesystem paths.

Users point the tool at their own local files at runtime. Public CI does not require those assets.

The repository hygiene check blocks common force-field/project extensions, known native-export filename patterns, and obvious personal absolute paths. This is a guardrail, not a license determination. Contributors remain responsible for verifying redistribution rights before submitting any data.

For public tests, prefer small synthetic fixtures with independently authored values and topology. Do not paste proprietary parameter tables into issues, pull requests, screenshots, or test fixtures.
