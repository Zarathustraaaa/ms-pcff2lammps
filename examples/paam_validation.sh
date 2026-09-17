#!/usr/bin/env bash
set -euo pipefail

: "${PCFF_OFF:?set PCFF_OFF to your licensed local pcff.off}"
: "${PCFF_BENDBEND_CSV:?set PCFF_BENDBEND_CSV to your local native Bend-Bend export}"
: "${PAAM_CAR:?set PAAM_CAR to the assigned validation CAR file}"
: "${PAAM_MDF:?set PAAM_MDF to the assigned validation MDF file}"

ms-pcff2lammps generate \
  --car "$PAAM_CAR" \
  --mdf "$PAAM_MDF" \
  --off "$PCFF_OFF" \
  --native-bendbend "$PCFF_BENDBEND_CSV" \
  --bendbend-profile paam-pentamer-20260917 \
  --forcite-missing-parameters 0 \
  --allow-forcite-cross-zero \
  --reference-profile paam-pentamer-20260917 \
  --outdir paam_validation
