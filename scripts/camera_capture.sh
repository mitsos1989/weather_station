#!/bin/bash

# Define the directory where images will be saved
IMG_DIR="/home/dimitris/weather_station/whole_sky_camera"

# Create the directory if it doesn't exist
mkdir -p "$IMG_DIR"

# Infinite loop to capture images every 5 minutes
while true; do
    # Get the current UTC hour (in 24-hour format)
    CURRENT_HOUR=$(date -u +"%H")
    
    # Check if current time is between 03 and 18 UTC
    if [ "$CURRENT_HOUR" -ge 3 ] && [ "$CURRENT_HOUR" -lt 18 ]; then
        # Get the current timestamp in the desired format
        TIMESTAMP=$(date +"%d-%m-%Y_%H:%M:%S")
        
        # Construct the output file path
        OUTPUT_FILE="$IMG_DIR/${TIMESTAMP}.jpg"
        
        # Capture the image with the specified settings
        libcamera-still --width 1920 --height 1080 --hdr --metering average --ev -1.5 --autofocus-mode manual --lens-position 0.05 --awb daylight --nopreview -o "$OUTPUT_FILE"
    else
        echo "Current UTC time ($CURRENT_HOUR) is outside the capture window. Skipping capture."
    fi
    
    # Delete only non-THUNDER images if there are more than 30 of them
    NON_THUNDER_IMAGES=$(ls -t "$IMG_DIR"/*.jpg 2>/dev/null | grep -v "/THUNDER")
    IMAGE_COUNT=$(echo "$NON_THUNDER_IMAGES" | wc -l)
    if [ "$IMAGE_COUNT" -gt 30 ]; then
        echo "$NON_THUNDER_IMAGES" | tail -n +31 | xargs rm --
    fi
    
    # Wait for 5 minutes before the next iteration
    sleep 300
done
