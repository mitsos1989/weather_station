import time
import board
import busio
import csv
from datetime import datetime, timezone
from digitalio import DigitalInOut, Direction, Pull
from adafruit_pm25.i2c import PM25_I2C

# Optional: connect to the RESET pin if available
reset_pin = None
# Uncomment and adjust if using a GPIO for reset:
# reset_pin = DigitalInOut(board.G0)
# reset_pin.direction = Direction.OUTPUT
# reset_pin.value = False

# Initialize I2C connection at 100KHz frequency and create PM2.5 sensor object
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
pm25 = PM25_I2C(i2c, reset_pin)

# Path to CSV file
csv_file_path = "/home/dimitris/weather_station/weather_station_data.csv"

print("Found PM2.5 sensor, reading data...")

while True:
    # Wait for 90 seconds between readings
    time.sleep(90)

    try:
        aqdata = pm25.read()
    except RuntimeError:
        print("Unable to read from sensor, retrying...")
        continue

    # Extract values (mapping sensor keys to PM measurements)
    pm1_value = aqdata["pm10 standard"]   # PM1.0
    pm25_value = aqdata["pm25 standard"]    # PM2.5
    pm10_value = aqdata["pm100 standard"]   # PM10.0

    # Optional: print sensor readings to the console for debugging
    print()
    print("Concentration Units (standard)")
    print("---------------------------------------")
    print("PM 1.0: %d\tPM2.5: %d\tPM10: %d" % (pm1_value, pm25_value, pm10_value))
    print("Concentration Units (environmental)")
    print("---------------------------------------")
    print("PM 1.0: %d\tPM2.5: %d\tPM10: %d" % (aqdata["pm10 env"], aqdata["pm25 env"], aqdata["pm100 env"]))
    print("---------------------------------------")
    print("Particles > 0.3um / 0.1L air:", aqdata["particles 03um"])
    print("Particles > 0.5um / 0.1L air:", aqdata["particles 05um"])
    print("Particles > 1.0um / 0.1L air:", aqdata["particles 10um"])
    print("Particles > 2.5um / 0.1L air:", aqdata["particles 25um"])
    print("Particles > 5.0um / 0.1L air:", aqdata["particles 50um"])
    print("Particles > 10 um / 0.1L air:", aqdata["particles 100um"])
    print("---------------------------------------")

    pm1_value_cal=pm1_value/10.0
    pm25_value_cal=pm25_value/10.0
    pm10_value_cal=pm10_value/10.0
    # Get the current timestamp in the required format
    #timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Create a row with the timestamp in column 1, 12 empty columns (columns 2-13),
    # and then PM1.0, PM2.5, and PM10.0 in columns 14, 15, and 16.
    row = [timestamp] + [""] * 12 + [pm1_value_cal, pm25_value_cal, pm10_value_cal]

    # Append the row to the CSV file
    try:
        with open(csv_file_path, "a", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(row)
        print("Data written to CSV:", row)
    except Exception as e:
        print("Failed to write to CSV:", e)
