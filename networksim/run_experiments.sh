#!/bin/bash

# Get accurate count of physical CPU cores (for information only)
PHYSICAL_CORES=$(lscpu -p | grep -v '^#' | sort -u -t, -k 2,2 | wc -l)
echo "Number of physical CPU cores: $PHYSICAL_CORES"

# Configuration - Accept parameters or use defaults
BASE_DIR=${1:-"/home/charlie/fyp/leoviz/positions/starlink_550_traffic_scaled"}

# Create a temporary directory for tracking progress
TEMP_DIR=$(mktemp -d)
PROGRESS_FILE="$TEMP_DIR/progress"
FAILED_FILE="$TEMP_DIR/failed_timestamps"
touch "$PROGRESS_FILE"
touch "$FAILED_FILE"

# Get timestamps from directory listing or timestamps.txt file
if [ -f "$BASE_DIR/timestamps.txt" ]; then
    TIMESTAMPS=($(cat "$BASE_DIR/timestamps.txt"))
    echo "Using timestamps from timestamps.txt file"
else
    # Get directories that are numeric (timestamps)
    TIMESTAMPS=($(find "$BASE_DIR" -maxdepth 1 -type d -name "[0-9]*" | xargs -n1 basename | sort -n))
    echo "Using timestamps from directory listing"
fi

TOTAL_SNAPSHOTS=${#TIMESTAMPS[@]}

# Setup cleanup trap
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Using sequential processing mode"
echo "Processing $TOTAL_SNAPSHOTS snapshots from $BASE_DIR"
echo "First timestamp: ${TIMESTAMPS[0]} ($(date -d @${TIMESTAMPS[0]}))"
echo "Last timestamp: ${TIMESTAMPS[-1]} ($(date -d @${TIMESTAMPS[-1]}))"

# Generate all job combinations up front
JOBS=()
TOTAL_JOBS=0

for timestamp in "${TIMESTAMPS[@]}"; do
    # Skip if timestamp directory doesn't exist
    if [ ! -d "$BASE_DIR/$timestamp" ]; then
        echo "Warning: Directory for timestamp $timestamp does not exist, skipping."
        continue
    fi
    
    # Skip if paths directory doesn't exist
    if [ ! -d "$BASE_DIR/$timestamp/paths" ]; then
        echo "Warning: No paths directory found for timestamp $timestamp, skipping."
        continue
    fi
    
    # Get all path directories for this timestamp
    PATH_DIRS=($(find "$BASE_DIR/$timestamp/paths" -maxdepth 1 -type d -name "path_*" | xargs -n1 basename))
    
    for path in "${PATH_DIRS[@]}"; do
        # Check for shortest.yaml
        if [ -f "$BASE_DIR/$timestamp/paths/$path/shortest.yaml" ]; then
            JOBS+=("$timestamp:$path:shortest")
            TOTAL_JOBS=$((TOTAL_JOBS + 1))
        fi
        
        # Check for spare.yaml
        if [ -f "$BASE_DIR/$timestamp/paths/$path/spare.yaml" ]; then
            JOBS+=("$timestamp:$path:spare")
            TOTAL_JOBS=$((TOTAL_JOBS + 1))
        fi
    done
done

echo "Total jobs to process: $TOTAL_JOBS"

if [ "$TOTAL_JOBS" -eq 0 ]; then
    echo "No jobs found to process. Please check your directory structure."
    exit 1
fi

echo "Starting sequential processing at $(date)"
echo "----------------------------------------"

# Process all jobs sequentially
COMPLETED=0
FAILED=0

for job in "${JOBS[@]}"; do
    IFS=':' read -r timestamp path yaml_type <<< "$job"
    
    # Setup paths
    config_file="$BASE_DIR/$timestamp/paths/$path/$yaml_type.yaml"
    output_dir="$BASE_DIR/$timestamp/paths/$path/$yaml_type"
    
    # Skip if yaml file doesn't exist
    if [ ! -f "$config_file" ]; then
        echo "Warning: Config file $config_file does not exist, skipping."
        continue
    fi
    
    # Create output directory if it doesn't exist
    mkdir -p "$output_dir"
    
    echo "Processing timestamp $timestamp, path $path, yaml $yaml_type"
    echo "Config: $config_file"
    echo "Output: $output_dir"
    
    # Ensure output directory has trailing slash for proper file placement
    if [[ "$output_dir" != */ ]]; then
        output_dir="${output_dir}/"
    fi
    
    # Execute the command directly
    if ./run_script.sh satsim -- --config="$config_file" --output-dir="$output_dir"; then
        echo "$timestamp:$path:$yaml_type" >> "$PROGRESS_FILE"
        COMPLETED=$((COMPLETED + 1))
        echo "Completed: $COMPLETED/$TOTAL_JOBS jobs"
    else
        echo "$timestamp:$path:$yaml_type" >> "$FAILED_FILE"
        FAILED=$((FAILED + 1))
        echo "Failed to process job: $timestamp:$path:$yaml_type"
    fi
    
    # Show progress
    echo "Progress: $COMPLETED/$TOTAL_JOBS completed, $FAILED failed"
done

echo -e "\n----------------------------------------"
echo "Processing complete at $(date)"

# Final statistics
echo "Summary:"
echo "- Successfully processed: $COMPLETED jobs"
echo "- Failed: $FAILED jobs"
if [ $FAILED -gt 0 ]; then
    echo "Failed jobs (timestamp:path:yaml_type):"
    cat "$FAILED_FILE"
    exit 1
fi