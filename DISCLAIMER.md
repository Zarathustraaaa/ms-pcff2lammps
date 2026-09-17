# Disclaimer

`ms-pcff2lammps` is research software for inspecting and translating molecular-mechanics parameter data. It is provided without a guarantee that a converted model is scientifically appropriate for a particular material, thermodynamic state, simulation protocol, or research conclusion.

A successful audit means that the software resolved the terms required by its implemented rules. It does **not** establish that:

- the source atom typing or charges are correct;
- every PCFF functional form or atom type is supported;
- a target chemistry lies inside the validated scope of this release;
- a LAMMPS production protocol is equivalent to a Materials Studio production protocol;
- energy agreement on one structure guarantees force agreement or transferability.

Users should retain the original Materials Studio files, preserve the generated parameter audit, and perform independent fixed-geometry energy and, where relevant, force checks before production use.

The project does not ship or sublicense Materials Studio or PCFF parameter databases. Users are responsible for ensuring that their local use of third-party files complies with the applicable software and data licenses.

Materials Studio, BIOVIA and PCFF are referenced only to describe interoperability. This project is not affiliated with or endorsed by Dassault Systèmes BIOVIA. LAMMPS is a separate project and is not bundled with this repository.

The BSD 3-Clause License contains the software warranty and liability disclaimer governing this repository. This document describes the intended scientific scope; it is not legal advice.
