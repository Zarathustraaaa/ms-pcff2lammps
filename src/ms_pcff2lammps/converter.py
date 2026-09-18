"""Compatibility facade for the converter API.

The implementation is split by responsibility, but existing imports from
``ms_pcff2lammps.converter`` remain supported.
"""

from .cli_impl import *

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
