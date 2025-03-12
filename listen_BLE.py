#!/usr/bin/env python3
import os
from bluezero import peripheral, adapter

# Define file location for storing sensor data
CSV_FILE = "/home/dimitris/weather_station/weather_station_data.csv"
os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

# Define UUIDs for the custom BLE service and characteristic.
DATA_SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
DATA_CHARACTERISTIC_UUID = "abcdef01-1234-5678-1234-56789abcdef0"

def write_callback(value, options):
    """
    Callback function triggered when the central device writes to the characteristic.
    'value' is a list of integers representing the received bytes.
    """
    data_str = ''.join(chr(b) for b in value)
    print("Received data:", data_str)
    # Append the data to the CSV file with a newline.
    with open(CSV_FILE, "a") as f:
        f.write(data_str + "\n")

# Convert the generator to a list to allow indexing.
ble_adapters = list(adapter.Adapter.available())
if not ble_adapters:
    print("No BLE adapter found. Ensure your Raspberry Pi's Bluetooth is enabled.")
    exit(1)

adapter_address = ble_adapters[0].address
print("Using BLE adapter with address:", adapter_address)

# Create the BLE peripheral with a local name.
ble_peripheral = peripheral.Peripheral(adapter_address, "ESP32_Receiver")

ble_peripheral.advertisement = {
    'local_name': "ESP32_Receiver",
    'service_uuid': DATA_SERVICE_UUID
}

# Add a service with the custom UUID.
ble_peripheral.add_service(srv_id=1, uuid=DATA_SERVICE_UUID, primary=True)

# Add a writable characteristic to the service.
ble_peripheral.add_characteristic(srv_id=1,
                                  chr_id=1,
                                  uuid=DATA_CHARACTERISTIC_UUID,
                                  value=[],          # Initial value (empty)
                                  notifying=False,
                                  flags=['write'],   # Allows write operations only
                                  write_callback=write_callback)

print("BLE server running. Waiting for data from ESP32 modules...")
# Publish the BLE peripheral (this call will block and run the event loop).
ble_peripheral.publish()
