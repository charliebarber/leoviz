#!/bin/bash

# Get number of CPU cores
NUM_CORES=$(nproc)
PHYSICAL_CORES=$(( NUM_CORES / 2 ))  # Assuming hyperthreading is enabled
echo "Number of CPU cores available: $NUM_CORES (likely $PHYSICAL_CORES physical cores)"

# Configuration
START_TIME=1737835561  # Current Unix timestamp
TOTAL_SNAPSHOTS=210
TIME_STEP=60
# Use number of physical cores + 20% for some overhead
NUM_PROCESSES=$(( (PHYSICAL_CORES * 120) / 100 ))

# Create a temporary directory for tracking progress
TEMP_DIR=$(mktemp -d)
PROGRESS_FILE="$TEMP_DIR/progress"
FAILED_FILE="$TEMP_DIR/failed_timestamps"
touch "$PROGRESS_FILE"
touch "$FAILED_FILE"

# Calculate end time
END_TIME=$((START_TIME + (TOTAL_SNAPSHOTS - 1) * TIME_STEP))

echo "Using $NUM_PROCESSES parallel processes (optimized for CPU-intensive workload)"
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

# No delay needed since we're not oversubscribing CPUs
parallel --will-cite -j "$NUM_PROCESSES" process_timestamp ::: $(seq $START_TIME $TIME_STEP $END_TIME)

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

# Cleanup
rm -rf "$TEMP_DIR"