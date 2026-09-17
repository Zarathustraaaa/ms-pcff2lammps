"""Console entry point for ms-pcff2lammps."""

from .converter import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
