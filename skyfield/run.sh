#!/bin/bash

# Get accurate count of physical CPU cores
PHYSICAL_CORES=$(lscpu -p | egrep -v '^#' | sort -u -t, -k 2,2 | wc -l)
echo "Number of physical CPU cores: $PHYSICAL_CORES"

# Configuration
START_TIME=1735689600 # 1st Jan 2025 00:00
TOTAL_SNAPSHOTS=110
TIME_STEP=60
NUM_PROCESSES=$PHYSICAL_CORES  # Use exactly one process per physical core

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

echo "Using $NUM_PROCESSES parallel processes (one per physical core)"
echo "Processing $TOTAL_SNAPSHOTS snapshots with ${TIME_STEP}s intervals"
echo "Start time: $(date -d @${START_TIME})"
echo "End time: $(date -d @${END_TIME})"

# Process a single timestamp
process_timestamp() {
    local timestamp=$1
    echo "Processing timestamp $timestamp ($(date -d @${timestamp}))"
    
    if python3 main.py --timestamp "$timestamp"; then
        echo "$timestamp" >> "$PROGRESS_FILE"
        local completed=$(wc -l < "$PROGRESS_FILE")
        echo "Completed: $completed/$TOTAL_SNAPSHOTS"
    else
        echo "$timestamp" >> "$FAILED_FILE"
        echo "Failed to process timestamp $timestamp"
    fi
}

# Export variables needed by parallel
export -f process_timestamp
export PROGRESS_FILE
export FAILED_FILE
export TOTAL_SNAPSHOTS

echo "Starting parallel processing at $(date)"
echo "----------------------------------------"

# Run parallel processes with basic optimized settings
parallel --will-cite \
         --jobs "$NUM_PROCESSES" \
         --progress \
         --load 100% \
         process_timestamp ::: $(seq $START_TIME $TIME_STEP $END_TIME)

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