"""Audited Materials Studio PCFF -> LAMMPS Class-II conversion utilities.

The implementation is deliberately conservative. Diagonal force-field terms
must resolve explicitly. Class-II cross terms are not silently converted to
zero unless the caller opts into a separately validated Forcite-backed policy.

This module does not assign atom types, generate charges, or redistribute PCFF
parameter databases. Users must provide their own legally obtained Materials
Studio structure and parameter files.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional


SECTION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*$")
FLOAT_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$")
OFF_TRUE_MISSING = "OFF_TRUE_MISSING"
REQUIRED_MISSING = "REQUIRED_MISSING"
CLASS2_CROSS_ZERO = "CLASS2_CROSS_ZERO"
# These are the Class-II coupling tables.  They are not diagonal terms:
# Forcite can legally evaluate a system with no record for one of these
# tuples (the contribution is then a no-op).  The converter must therefore
# keep them distinct from a missing bond/angle/torsion/inversion coefficient.
CLASS2_CROSS_INTERACTIONS = {
    "BondBond",
    "BondAngle",
    "BondBond13",
    "MiddleBondTorsion",
    "EndBondTorsion",
    "AngleTorsion",
    "AngleAngleTorsion",
    "AngleAngle",
}

PARITY_TOLERANCE_KCAL_MOL = 1.0e-3
__version__ = "0.1.0b1"

# The native Bend-Bend sequence mapping/no-op allowlist below was established
# by a cross-geometry fit and independent run-0 parity checks for this profile.
# It is not applied to arbitrary chemistry.
BEND_BEND_PROFILES = {"paam-pentamer-20260917"}


@dataclass
class OffRecord:
    section: str
    line_start: int
    raw_lines: list[str]
    tokens: list[str]


@dataclass
class OffSection:
    name: str
    start_line: int
    end_line: int
    raw_lines: list[str]
    records: list[OffRecord]


@dataclass
class Atom:
    id: int
    name: str
    element: str
    ms_type: str
    charge: float
    x: float
    y: float
    z: float


@dataclass
class Bond:
    id: int
    i: int
    j: int
    order: float


@dataclass
class MolecularSystem:
    atoms: dict[int, Atom]
    bonds: list[Bond]
    cell: Optional[tuple[float, float, float, float, float, float]]
    pbc: bool


@dataclass
class Match:
    section: str
    requested: tuple[str, ...]
    matched: Optional[OffRecord]
    oriented_types: Optional[tuple[str, ...]] = None
    reversed_order: bool = False


@dataclass
class AuditRow:
    interaction: str
    atom_ids: str
    ms_atom_types: str
    match_level: str
    matched_off_record: str
    coefficient_values: str
    zero_source: str
    status: str


@dataclass
class OffParameter:
    section: str
    types: tuple[str, ...]
    form: str
    values: tuple[str, ...]
    record: OffRecord
    ignored: bool = False


@dataclass
class EquivalenceRule:
    source: str
    role: str
    targets: tuple[str, ...]
    record: OffRecord


@dataclass
class StepDownRule:
    section: str
    line_start: int
    pattern: tuple[int, ...]
    level: str
    raw: str = ""


@dataclass(frozen=True)
class StepDownEvaluation:
    rule: StepDownRule
    applicable: bool
    reason: str
    query: Optional[tuple[str, ...]] = None
    candidates: tuple[SearchQuery, ...] = ()


@dataclass(frozen=True)
class BondTypeEquivalenceRule:
    source: str
    targets: tuple[str, ...]
    record: OffRecord


@dataclass(frozen=True)
class SearchQuery:
    query: tuple[str, ...]
    match_level: str
    reversed_order: bool
    atom_levels: tuple[int, ...]
    bond_levels: tuple[int, ...] = ()


# These mappings only name the OFF table already used by the audit.  They do
# not add a fallback or create a parameter for a missing interaction.
INTERACTION_SECTION = {
    "nonbond": "DIAGONAL_VDW",
    "bond": "BOND_STRETCH",
    "angle": "ANGLE_BEND",
    "BondBond": "STRETCH_STRETCH",
    "BondAngle": "STRETCH_BEND_STRETCH",
    "dihedral": "TORSIONS",
    "MiddleBondTorsion": "TORSION_STRETCH",
    "EndBondTorsion": "STRETCH_TORSION_STRETCH",
    "BondBond13": "SEPARATED_STRETCH_STRETCH",
    "AngleTorsion": "BEND_TORSION_BEND",
    "AngleAngleTorsion": "TORSION_BEND_BEND",
    "improper": "INVERSIONS",
    "AngleAngle": "BEND_BEND",
}

SECTION_EQUIVALENCE = {
    "DIAGONAL_VDW": ("EQUIVALENCE_OFF_DIAGONAL_VDW", "all"),
    "BOND_STRETCH": ("EQUIVALENCE_BOND", "bond"),
    "ANGLE_BEND": ("EQUIVALENCE_ANGLE", "angle"),
    "STRETCH_STRETCH": ("EQUIVALENCE_ANGLE", "angle"),
    "STRETCH_BEND_STRETCH": ("EQUIVALENCE_ANGLE", "angle"),
    "TORSIONS": ("EQUIVALENCE_TORSION", "torsion"),
    "TORSION_STRETCH": ("EQUIVALENCE_TORSION", "torsion"),
    "STRETCH_TORSION_STRETCH": ("EQUIVALENCE_TORSION", "torsion"),
    "SEPARATED_STRETCH_STRETCH": ("EQUIVALENCE_TORSION", "torsion"),
    "BEND_TORSION_BEND": ("EQUIVALENCE_TORSION", "torsion"),
    "TORSION_BEND_BEND": ("EQUIVALENCE_TORSION", "torsion"),
    "INVERSIONS": ("EQUIVALENCE_INVERSION", "inversion"),
    "BEND_BEND": ("EQUIVALENCE_INVERSION", "inversion"),
}


SECTION_STEP_DOWN = {
    "DIAGONAL_VDW": "STEP_DOWN_OFF_DIAGONAL_VDW",
    "BOND_STRETCH": "STEP_DOWN_BOND",
    "ANGLE_BEND": "STEP_DOWN_ANGLE",
    "STRETCH_STRETCH": "STEP_DOWN_ANGLE",
    "STRETCH_BEND_STRETCH": "STEP_DOWN_ANGLE",
    "TORSIONS": "STEP_DOWN_TORSION",
    "TORSION_STRETCH": "STEP_DOWN_TORSION",
    "STRETCH_TORSION_STRETCH": "STEP_DOWN_TORSION",
    "SEPARATED_STRETCH_STRETCH": "STEP_DOWN_TORSION",
    "BEND_TORSION_BEND": "STEP_DOWN_TORSION",
    "TORSION_BEND_BEND": "STEP_DOWN_TORSION",
    "INVERSIONS": "STEP_DOWN_INVERSION",
    "BEND_BEND": "STEP_DOWN_INVERSION",
}

__all__ = [name for name in globals() if not name.startswith("__") or name == "__version__"]
