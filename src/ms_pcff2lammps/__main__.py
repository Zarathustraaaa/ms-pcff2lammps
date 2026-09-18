"""Allow ``python -m ms_pcff2lammps`` to invoke the command-line interface."""

from .cli import main

raise SystemExit(main())
