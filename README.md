# Krini Weather Station Project 🌦️

This repository contains the scripts and configuration files for my custom-built weather station located in Kalamaria, Thessaloniki, Greece. The station is built on a Raspberry Pi 4 and utilizes a variety of sensors to collect real-time atmospheric data.

## 🔴 Live Data

Real-time data from the station is visualized and shared publicly on my website:

**➡️ [weather-krini.ngrok.io](http://weather-krini.ngrok.io)**

## 🛠️ Hardware Components

The station is a hybrid system using a central Raspberry Pi and remote ESP32 boards for sensor data collection.

### Core Components
* **Host Computer**: Raspberry Pi 4 4GB
* **Camera**: Camera Module 3 (Wide) pointing at the zenith for cloud and lightning observation.

### Primary Sensors (Connected to RPi)
* **Wind**: Cup Anemometer & Wind Vane
* **Air Quality**: Adafruit PMSA003I Air Quality Breakout
* **Lightning**: DFRobot Gravity: Lightning Sensor
* **Precipitation**: DFRobot Gravity: Tipping Bucket Rainfall Sensor

### Remote Sensors (via ESP32 Boards)
* **Atmospherics**: Waveshare BME280 (Temperature, Humidity, Pressure)
* **Temperature**: MCP9808 High Accuracy Temperature Sensor
* **UV Light**: ML8511 UV Sensor
* **Ambient Light**: VEML6030 Ambient Light Sensor
* **Rain Detection**: LM393 / FC-37 Rain Sensor

## 💻 Software & Technology

* **Primary Language**: Python
* **Data Acquisition**: Scripts to interface with I2C, UART, and GPIO sensors.
* **Web Visualization**: Data is plotted using the `plotly` library.
* **Web Hosting**: The local website is exposed to the internet using `ngrok`.
* **Operating System**: MX Linux on my development machine.

## 📂 Repository Contents

This repository, `weather_station`, includes:
* Python scripts for reading sensor data.
* Data parsing and logging tools.
* Configuration files for the station.


## About the Author

This project was designed and built by a meteorologist with an expertise in sub-seasonal forecasting.

---
*README created on August 3, 2025.*
