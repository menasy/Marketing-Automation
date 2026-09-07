#!/usr/bin/env sh
# Zero-Touch n8n Workflow Auto-Import Helper Script
set -eu

WORKFLOW_FILE="${1:-/automation/workflow.json}"

echo "=================================================="
echo "   Marketing Automation n8n Zero-Touch Setup      "
echo "=================================================="

if [ ! -f "$WORKFLOW_FILE" ]; then
    echo "Error: Workflow file not found at $WORKFLOW_FILE" >&2
    exit 1
fi

echo "Importing workflow from $WORKFLOW_FILE..."
n8n import:workflow --input="$WORKFLOW_FILE"

echo "Activating imported workflows..."
n8n update:workflow --all --active=true || true

echo "Zero-touch n8n workflow setup successfully completed."
