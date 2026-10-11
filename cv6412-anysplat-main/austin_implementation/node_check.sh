#!/bin/bash

echo "--- Checking available GPU Nodes Individually ---"

# Define the partitions we are interested in
PARTITIONS=("gpu" "gpush" "short" "preempt" "normal")

# Temporary file to store raw sinfo output lines
RAW_SINFO_OUTPUT=$(mktemp)

# Function to query and process a partition's data
check_partition() {
    local part=$1
    # Capture the output with format: Nodelist Gres State Reason (no headers)
    sinfo -p $part -h -o "%N %G %T %R" | grep gpu >> $RAW_SINFO_OUTPUT
}

# Iterate over all partitions to fill the raw data file
for p in "${PARTITIONS[@]}"; do
    check_partition $p
done

echo ""
echo "--- Summary of Available Nodes (Idle/Mixed) ---"
echo "Node Name             GPU/GRES                      State"
echo "---------------------------------------------------------"

# Read the raw data line by line
sort -u $RAW_SINFO_OUTPUT | while read nodelist gres state reason; do
    # Only process nodes that are idle or mixed (available for jobs)
    # idle~ = powered down but schedulable; mixed- = draining, skip it
    if [[ "$state" =~ ^(idle|mixed)(~)?$ ]]; then
        # Expand the compressed nodelist using scontrol
        scontrol show hostnames $nodelist | while read hostname; do
            # Print each individual hostname with its details
            printf "%-20s  %-30s  %-10s\n" "$hostname" "$gres" "$state"
        done
    fi
done

# Clean up temporary file
rm $RAW_SINFO_OUTPUT
