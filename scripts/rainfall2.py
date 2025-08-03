#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''!
  @file  read_data.py
  @brief Get the raw data, which is the tipping bucket count of rainfall, in units of counts.
  @copyright   Copyright (c) 2021 DFRobot Co.Ltd (http://www.dfrobot.com)
  @license     The MIT License (MIT)
  @author      [fary](feng.yang@dfrobot.com)
  @version     V1.1
  @date        2023-01-28
  @url         https://github.com/DFRobor/DFRobot_RainfallSensor
'''
from __future__ import print_function
import sys
sys.path.append("../")
import time
import datetime
import csv

from DFRobot_RainfallSensor import *

# You can choose UART or I2C as needed
# sensor = DFRobot_RainfallSensor_UART()
sensor = DFRobot_RainfallSensor_I2C()

# Path to the CSV file for logging
CSV_FILE_PATH = "/home/dimitris/weather_station/weather_station_data.csv"

# Global variables to store baseline values and previous readings
baseline_rainfall = None  # Baseline reading at the beginning of the day
last_rainfall = None      # Last recorded rainfall (in mm)
last_time = None          # Time of last reading (in seconds)
raw_data_prev = None      # Previous raw tipping bucket count
current_day = None        # To track the current day in UTC

def initialize_day():
    """
    Initialize or reset the baseline at the beginning of a new day.
    This version uses UTC for the date.
    """
    global baseline_rainfall, current_day
    current_day = datetime.datetime.utcnow().date()
    baseline_rainfall = sensor.get_rainfall()
    print("New day detected (UTC). Baseline rainfall set to: %f mm" % baseline_rainfall)

def setup():
    """
    Set up the sensor and initialize the baseline and previous reading values.
    """
    global last_rainfall, last_time, raw_data_prev
    while not sensor.begin():
        print("Sensor initialize failed!!")
        time.sleep(1)
    print("Sensor initialize success!!")
    print("Version: " + sensor.get_firmware_version())
    print("vid: %#x" % sensor.vid)
    print("pid: %#x" % sensor.pid)
    
    # Set the baseline for daily accumulation using UTC day
    initialize_day()
    
    # Initialize previous values for intensity calculation
    last_rainfall = sensor.get_rainfall()
    last_time = time.time()
    raw_data_prev = sensor.get_raw_data()

def log_to_csv(timestamp, daily_total):
    """
    Log the current timestamp (in UTC) and daily total precipitation to the CSV file.
    The timestamp is stored in the first column and daily_total in the 11th column.
    """
    # Create a row with 11 columns:
    # - First column: timestamp
    # - Columns 2 to 10: empty strings
    # - Column 11: daily_total (as string, without unit)
    row = [timestamp] + [""] * 9 + [str(daily_total)]
    try:
        with open(CSV_FILE_PATH, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(row)
        print("Logged data to CSV:", row)
    except Exception as e:
        print("Error writing to CSV file:", e)

def loop():
    """
    Main loop that reads sensor data, calculates rain intensity (mm/h) based on the time difference
    between readings, computes the total precipitation since midnight (UTC), and logs new tipping events.
    """
    global last_rainfall, last_time, raw_data_prev, current_day, baseline_rainfall
    current_time = time.time()
    # Use UTC time for logging
    current_datetime = datetime.datetime.utcnow()
    
    # Check if a new UTC day has started
    if datetime.datetime.utcnow().date() != current_day:
        initialize_day()
    
    # Get sensor measurements
    workingtime = sensor.get_sensor_working_time()  # Sensor operating time in hours
    current_rainfall = sensor.get_rainfall()        # Total rainfall in mm (cumulative)
    
    # Calculate rain intensity (mm/h) using the difference over time
    time_diff = current_time - last_time
    if time_diff > 0:
        intensity = (current_rainfall - last_rainfall) / time_diff * 3600
    else:
        intensity = 0.0
    
    # Calculate total precipitation since the beginning of the day (UTC)
    daily_total = current_rainfall - baseline_rainfall
    
    # Example: Get rainfall in the past hour (if available)
    one_hour_rainfall = sensor.get_rainfall_time(1)
    # Get the raw tipping bucket count
    current_raw = sensor.get_raw_data()
    
    # Display the readings
    print("Working time         : %f H" % workingtime)
    print("Total Rainfall       : %f mm" % current_rainfall)
    print("Rainfall in one hour : %f mm" % one_hour_rainfall)
    print("Daily Total          : %f mm" % daily_total)
    print("Rain intensity       : %f mm/h" % intensity)
    print("Raw tipping bucket   : %d" % current_raw)
    print("--------------------------------------------------------------------")
    
    # Check if the tipping bucket has just tipped (i.e. raw data has changed)
    if current_raw != raw_data_prev:
        # --- MODIFICATION START ---
        # Validate the daily_total before logging to avoid erroneous data.
        # Only log if the value is between 0 and 1000 (inclusive).
        if 0 <= daily_total <= 1000:
            # Log the event with the current UTC timestamp and daily total
            timestamp_str = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            log_to_csv(timestamp_str, daily_total)
        else:
            # If the value is out of range, print a message and do not log it.
            print(f"Skipping log: daily_total ({daily_total} mm) is out of the valid range [0, 1000].")
        # --- MODIFICATION END ---
        
        raw_data_prev = current_raw
    
    # Update previous values for next iteration
    last_rainfall = current_rainfall
    last_time = current_time
    
    time.sleep(60)

if __name__ == "__main__":
    setup()
    while True:
        loop()
