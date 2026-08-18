#!/usr/bin/env bash
# Generates a synthetic weekly batch using Synthea and copies the six
# in-scope CSVs into data/landing/<run_id>/ for local testing.
#
# Requires Java 11+ and the Synthea jar (https://github.com/synthetichealth/synthea).
#
# Usage:
#   ./scripts/generate_synthea_data.sh <num_patients> <run_id>

set -euo pipefail
NUM_PATIENTS="${1:-100}"
RUN_ID="${2:-$(date +%F)}"
OUT_DIR="data/landing/${RUN_ID}"

mkdir -p "$OUT_DIR"

# TODO: point SYNTHEA_JAR at your local build/download
SYNTHEA_JAR="${SYNTHEA_JAR:-./synthea-with-dependencies.jar}"
java -jar "$SYNTHEA_JAR" -p "$NUM_PATIENTS" --exporter.csv.export true

# Synthea writes to ./output/csv by default - copy only the six in-scope files
for f in organizations providers payers patients encounters conditions; do
  cp "output/csv/${f}.csv" "${OUT_DIR}/${f}.csv"
done

echo "Synthetic batch ready at ${OUT_DIR}"
