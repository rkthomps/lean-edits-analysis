#!/bin/bash

set -u

VERSIONS_FILE="VERSIONS.txt"

if [ ! -f "$VERSIONS_FILE" ]; then
    echo "Error: $VERSIONS_FILE not found!"
    exit 1
fi

declare -A RESULTS

while read -r v; do
    [[ -z "$v" ]] && continue # Skip empty lines
    tc="leanprover/lean4:v${v}"
    echo "Checking version $v..."
    if elan run $tc lake build; then
        RESULTS["$v"]="build  ✅ "
    else
        RESULTS["$v"]="build  ❌ "
    fi

    if elan run $tc lake exe tests; then
        RESULTS["$v"]="${RESULTS[$v]}, tests  ✅ "
    else
        RESULTS["$v"]="${RESULTS[$v]}, tests  ❌ "
    fi
done < "$VERSIONS_FILE" 

echo "Results:"
for v in "${!RESULTS[@]}"; do
    echo "Version $v: ${RESULTS[$v]}"
done



