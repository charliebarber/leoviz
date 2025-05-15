#!/bin/bash
# Configuration
START_TIME=1735689600 # 1st Jan 2025 00:00
TOTAL_SNAPSHOTS=110
TIME_STEP=60

# Create a temporary directory for tracking progress
TEMP_DIR=$(mktemp -d)
PROGRESS_FILE="$TEMP_DIR/progress"
FAILED_FILE="$TEMP_DIR/failed_timestamps"
touch "$PROGRESS_FILE"
touch "$FAILED_FILE"

# Calculate end time
END_TIME=$((START_TIME + (TOTAL_SNAPSHOTS - 1) * TIME_STEP))

# Setup cleanup trap
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Processing $TOTAL_SNAPSHOTS snapshots with ${TIME_STEP}s intervals"
echo "Start time: $(date -d @${START_TIME})"
echo "End time: $(date -d @${END_TIME})"
echo "Starting sequential processing at $(date)"
echo "----------------------------------------"

# Process timestamps sequentially
for timestamp in $(seq $START_TIME $TIME_STEP $END_TIME); do
    echo "Processing timestamp $timestamp ($(date -d @${timestamp}))"
    
    if python3 main.py --timestamp "$timestamp" --num-eval-pairs 0; then
        echo "$timestamp" >> "$PROGRESS_FILE"
        completed=$(wc -l < "$PROGRESS_FILE")
        echo "Completed: $completed/$TOTAL_SNAPSHOTS"
    else
        echo "$timestamp" >> "$FAILED_FILE"
        echo "Failed to process timestamp $timestamp"
    fi
done

echo -e "\n----------------------------------------"
echo "Processing complete at $(date)"

# Final statistics
COMPLETED=$(wc -l < "$PROGRESS_FILE")
FAILED=$(wc -l < "$FAILED_FILE")
echo "Summary:"
echo "- Successfully processed: $COMPLETED snapshots"
echo "- Failed: $FAILED snapshots"
if [ $FAILED -gt 0 ]; then
    echo "Failed timestamps:"
    cat "$FAILED_FILE"
    exit 1
fi