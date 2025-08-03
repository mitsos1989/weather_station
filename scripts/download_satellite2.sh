#!/bin/bash

# Base URL parts
BASE_URL_PREFIX="https://imn-api.meteoplaza.com/v4/nowcast/tiles/satellite-europe/"
TILE_INFO="/7/47/70/51/75?outputtype=jpeg" # Adjust tile numbers if needed for your specific view

# Define the output directory and file name
OUTPUT_DIR="/home/dimitris/weather_station/satellite_latest"
OUTPUT_FILE="satellite_greece.jpg"
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILE"

# Ensure the output directory exists
mkdir -p "$OUTPUT_DIR"

while true; do
    # --- Calculate the timestamp for the latest available image ---
    # Get current UTC time components
    CURRENT_YEAR=$(date -u +%Y)
    CURRENT_MONTH=$(date -u +%m)
    CURRENT_DAY=$(date -u +%d)
    CURRENT_HOUR=$(date -u +%H)
    CURRENT_MINUTE=$(date -u +%M)

    # Calculate the minute of the last 15-minute interval (00, 15, 30, 45)
    # Integer division gives the number of full 15-min intervals passed in the hour
    INTERVAL_NUM=$((CURRENT_MINUTE / 65))
    # Multiply by 15 to get the starting minute of that interval
    TARGET_MINUTE_NUM=$((INTERVAL_NUM * 65))
    # Format the minute to have a leading zero if needed (e.g., 00, 05 -> 00, 15)
    TARGET_MINUTE=$(printf "%02d" $TARGET_MINUTE_NUM)

    # Construct the timestamp string in YYYYMMDDHHMM format
    LATEST_TIMESTAMP="${CURRENT_YEAR}${CURRENT_MONTH}${CURRENT_DAY}${CURRENT_HOUR}${TARGET_MINUTE}"
    # --- End Timestamp Calculation ---

    # Construct the full dynamic URL for the latest image
    CURRENT_IMAGE_URL="${BASE_URL_PREFIX}${LATEST_TIMESTAMP}${TILE_INFO}"

    echo "$(date): Downloading image for timestamp $LATEST_TIMESTAMP..."
    echo "URL: $CURRENT_IMAGE_URL"
    echo "Saving to: $OUTPUT_PATH"

    # Download the image using curl
    # -f makes curl fail silently on server errors (like 404 Not Found)
    # -L follows redirects if any
    curl -f -L -s -o "$OUTPUT_PATH" "$CURRENT_IMAGE_URL"

    # Check curl's exit status
    if [ $? -eq 0 ]; then
        # Optional: Add a check for file size > 0 to ensure it's not an empty file
        if [ -s "$OUTPUT_PATH" ]; then
            echo "$(date): Download successful for $LATEST_TIMESTAMP."
        else
            echo "$(date): Download failed for $LATEST_TIMESTAMP (empty file received). Image might not be available yet."
            # Optional: remove the empty file if created
            rm -f "$OUTPUT_PATH"
        fi
    else
        # Common curl error codes: 22 (HTTP page not retrieved, e.g., 404), 6 (Could not resolve host), 7 (Failed to connect to host)
        echo "$(date): Download failed for $LATEST_TIMESTAMP (curl error code $?). Check URL or network. Retrying in 15 minutes."
    fi

    # Images update every 15 minutes, so wait 15 minutes before the next attempt.
    echo "$(date): Waiting 15 minutes (900 seconds) before the next download... "
    sleep 900
done
