#!/bin/bash

# Configuration
START_TIME=1735689600 # 1st Jan 2025 00:00
TOTAL_SNAPSHOTS=110
TIME_STEP=60

# Create temporary directory for job management
TEMP_DIR=$(mktemp -d)

# Create servers.txt with correct GNU Parallel format for 8 cores each
cat > "$TEMP_DIR/servers.txt" << 'EOL'
8/canada-l.cs.ucl.ac.uk
8/mandarin-l.cs.ucl.ac.uk
8/pintail-l.cs.ucl.ac.uk
8/wigeon-l.cs.ucl.ac.uk
EOL

echo "Starting distributed processing"
echo "Processing $TOTAL_SNAPSHOTS snapshots"
echo "Start time: $(date -d @${START_TIME})"

# The main parallel execution
parallel --will-cite \
         --progress \
         --slf "$TEMP_DIR/servers.txt" \
         --transferfile "./main.py" \
         --transferfile "./ground_stations.py" \
         --transferfile "./satellite_network.py" \
         --transferfile "./tle_parser.py" \
         --transferfile "./cities.csv" \
         --transferfile "./cities_scaled.csv" \
         --transferfile "./requirements.txt" \
         --return "output_{}/*" \
         --workdir "/tmp/skyfield_{}" \
         --load 80% \
         --cleanup \
         --joblog "$TEMP_DIR/parallel.log" \
         'setenv TIMESTAMP {}; \
          echo "Setting up Python environment for timestamp $TIMESTAMP on `hostname`..."; \
          python3 -m venv venv; \
          source venv/bin/activate.csh; \
          pip install -r requirements.txt; \
          mkdir -p output_$TIMESTAMP; \
          taskset -c 0,2,4,6,8,10,12,14 python main.py --timestamp $TIMESTAMP --output output_$TIMESTAMP/output.txt; \
          deactivate; \
          echo "Completed timestamp $TIMESTAMP on `hostname`"' \
         ::: $(seq $START_TIME $TIME_STEP $END_TIME)

if [ -f "$TEMP_DIR/parallel.log" ]; then
    FAILED=$(grep -c "1$" "$TEMP_DIR/parallel.log" || true)
    if [ -n "$FAILED" ] && [ "$FAILED" -gt 0 ]; then
        echo "Failed jobs: $FAILED"
        echo "Check parallel.log for details"
        exit 1
    fi
fi