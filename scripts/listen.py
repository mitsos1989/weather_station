import socket

HOST = ''  # Listen on all available interfaces
PORT = 12345
CSV_FILE = "/home/dimitris/weather_station/weather_station_data.csv"

# Ensure the directory exists
import os
os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(5)
    print("TCP Server listening on port", PORT)
    while True:
        conn, addr = s.accept()
        with conn:
            print("Connected by", addr)
            data = conn.recv(1024)
            if data:
                # Append received data to CSV file
                with open(CSV_FILE, "a") as f:
                    f.write(data.decode('utf-8'))
                # Send a simple acknowledgement
                conn.sendall(b"OK")
