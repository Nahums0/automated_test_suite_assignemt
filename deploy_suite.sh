#!/bin/bash

EXE_URI="$1"
TENANT_ID="$2"

EXE_PATH="/tmp/sensor"
LOGS_OUTPUT_PATH="/var/log/sensor_logs.log"

# Download the executable
wget "$EXE_URI" -O "$EXE_PATH" > /dev/null
exitCode=$?

if [ $exitCode -ne 0 ]; then
    echo "Error: Failed to download the executable from $EXE_URI"
    exit 1
fi

# Change file's permission to make it executable
chmod +x "$EXE_PATH" > /dev/null
exitCode=$?

if [ $exitCode -ne 0 ]; then
    echo "Error: Failed to set execute permissions on $EXE_PATH"
    exit 1
fi

# Run the executable
"$EXE_PATH" --logs-output-path "$LOGS_OUTPUT_PATH"
exitCode=$?

if [ $exitCode -ne 0 ]; then
    echo "Error: Failed to execute $EXE_PATH"
    exit 1
fi

# Read outputted log file
if [[ -f "$LOGS_OUTPUT_PATH" ]]; then
    cat "$LOGS_OUTPUT_PATH"
else
    echo "Error: Failed to find log file at $LOGS_OUTPUT_PATH"
    exit 1
fi
