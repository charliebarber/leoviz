#!/bin/bash
# Check if filename argument is provided
if [ $# -lt 1 ]; then
    echo "Usage: ./run_script.sh <file_or_directory> [additional args]"
    exit 1
fi

# Get the name and remove it from args
NAME=$1
shift

# Check if source exists in scripts/
if [ ! -e "scripts/${NAME}" ]; then
    echo "Error: ${NAME} not found in scripts/ directory"
    exit 1
fi

# Handle differently based on whether it's a file or directory
if [ -d "scripts/${NAME}" ]; then
    # Directory case
    rm -rf "ns-3.43/scratch/${NAME}"
    cp -r "scripts/${NAME}" "ns-3.43/scratch/"
else
    # Single file case
    cp "scripts/${NAME}" "ns-3.43/scratch/"
fi

# Run the script with any additional arguments
cd ns-3.43
./ns3 run "${NAME}" $@

# Clean up based on type
cd ..  # Go back to parent directory
if [ -d "scripts/${NAME}" ]; then
    rm -rf "ns-3.43/scratch/${NAME}"
else
    rm "ns-3.43/scratch/${NAME}"
fi