import os
import pandas as pd
import psycopg2

DATABASE_URL = 'postgres://u88utsh7ahek8e:p643e88d3875d32d1bc9562e051f2229aec2be550d6d3bbeeb602b0ee255a2a36@c9tiftt16dc3eo.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/d9fd97gi2i84oh'

def update_db_from_csv():
    # Read the CSV file (ensure it's in the repository or accessible location)
    df = pd.read_csv("weather_station_data.csv", parse_dates=["timestamp"])
    
    # Connect to the database
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Loop through each row in the CSV
    for index, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO weather_data (timestamp, temperature1, humidity, pressure, light_intensity, rain_event, temperature2, uv, rain_accumulation, wind_speed, wind_direction, pm1, pm25, pm10)
            VALUES (%s, %s, %s, %s, %s,%s, %s,%s, %s,%s, %s,%s, %s,%s)
            ON CONFLICT (timestamp) DO UPDATE
            SET temperature1 = EXCLUDED.temperature1,
                humidity = EXCLUDED.humidity,
                pressure = EXCLUDED.pressure,
                light_intensity = EXCLUDED.light_intensity,
                rain_event = EXCLUDED.rain_event,
                temperature2 = EXCLUDED.temperature2,
                uv = EXCLUDED.uv,
                rain_accumulation = EXCLUDED.rain_accumulation,
                wind_speed = EXCLUDED.wind_speed,
                wind_direction = EXCLUDED.wind_direction,
                pm1 = EXCLUDED.pm1,
                pm25 = EXCLUDED.pm25,
                pm10 = EXCLUDED.pm10;
            """,
            (
                row["timestamp"],
                row.get("Temperature (BME280) (°C)"),
                row.get("Humidity (BME280) (%)"),
                row.get("Pressure (BME280) (hPa)"),
                row.get("Light Intensity (BH1750) (lux)"),
                row.get("Rain Event (LM393)"),
                row.get("Temperature (MCP9808) (°C)"),
                row.get("UV Index (GY-8511)"),
                row.get("Rain Accumulation (SEN0575) (mm)"),
                row.get("Wind Speed (Anemometer) (m/s)"),
                row.get("Wind Direction (Wind Vane) (deg)"),
                row.get("PM1.0 (PMSA003I) (µg/m³)"),
                row.get("PM2.5 (PMSA003I) (µg/m³)"),
                row.get("PM10.0 (PMSA003I) (µg/m³)"),
            )
        )
    
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    update_db_from_csv()
