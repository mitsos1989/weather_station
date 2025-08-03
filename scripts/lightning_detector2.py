import sys
import time
import csv
import subprocess
from datetime import datetime
from DFRobot_AS3935_Lib import DFRobot_AS3935
import RPi.GPIO as GPIO

# I2C address
AS3935_I2C_ADDR1 = 0X01
AS3935_I2C_ADDR2 = 0X02
AS3935_I2C_ADDR3 = 0X03

# Antenna tuning capacitance (must be integer multiple of 8, 8 - 120 pf)
AS3935_CAPACITANCE = 96
IRQ_PIN = 11

GPIO.setmode(GPIO.BOARD)
sensor = DFRobot_AS3935(AS3935_I2C_ADDR3, bus=1)
if sensor.reset():
    print("init sensor success.")
else:
    print("init sensor fail")
    while True:
        pass

# 1) Power up and configure the AS3935 as before
sensor.power_up()
sensor.set_outdoors()
#sensor.disturber_dis()
sensor.disturber_en()
sensor.set_tuning_caps(AS3935_CAPACITANCE)
sensor.set_noise_floor_lv1(2)
sensor.set_watchdog_threshold(2)
sensor.set_spike_rejection(2)




def callback_handle(channel):
    global sensor
    time.sleep(0.008)
    intSrc = sensor.get_interrupt_src()
    if intSrc == 1:
        lightning_distKm = sensor.get_lightning_distKm()
        print('Lightning occurs!')
        print('Distance: %dkm' % lightning_distKm)
        lightning_energy_val = sensor.get_strike_energy_raw()
        print('Intensity: %d' % lightning_energy_val)
        
        # Get the current timestamp for both CSV and image naming.
        now = datetime.utcnow()
        timestamp_csv = now.strftime("%Y-%m-%d %H:%M:%S")
        print("Timestamp for logging:", timestamp_csv)
        
        # Append the data to the CSV file.
        csv_file = "/home/dimitris/weather_station/weather_station_data.csv"
        try:
            # Prepare a row with 7 columns where only columns 1, 6 and 7 are filled.
            row = [timestamp_csv, "", "", "", "", "Lightning is Detected", lightning_distKm]
            with open(csv_file, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(row)
            print("Data logged to CSV.")
        except Exception as e:
            print("Failed to write to CSV:", e)
        
        # Build the image filename.
        # For the file name, we format the timestamp in a file-friendly manner.
        timestamp_img = now.strftime("%Y%m%d_%H%M%S")
        img_filename = f"/home/dimitris/weather_station/whole_sky_camera/THUNDER_{timestamp_img}.jpg"
        bash_cmd = f"libcamera-still -n --immediate --hdr --denoise cdn_off --autofocus-mode manual --lens-position 0.05 --shutter 500000 --gain 1  --width 1920 --height 1080 --nopreview  -o {img_filename}"
        try:
            subprocess.run(bash_cmd, shell=True, check=True)
            print("Image captured and saved as:", img_filename)
        except subprocess.CalledProcessError as e:
            print("Failed to capture image:", e)
        
    elif intSrc == 2:
        print('Disturber discovered!')
    elif intSrc == 3:
        print('Noise level too high!')
    else:
        pass

# 3) ----- GPIO SETUP WITH PULL-DOWN -----
# Replace your old setup line with this one:
#GPIO.setup(IRQ_PIN, GPIO.IN)
GPIO.setup(IRQ_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
# (This ties the line low until the AS3935 actively drives it high) :contentReference[oaicite:2]{index=2}
GPIO.add_event_detect(IRQ_PIN, GPIO.RISING, callback=callback_handle)
print("GPIO pulled down + callback attached.")
'''
# 2) ----- SELF-TEST PHASE -----
# Temporarily drive the SRCO (1.1 MHz) oscillator out on IRQ so you can verify wiring
print("→ Self-test: you should see callbacks for SRCO pulses now.")
sensor.set_irq_output_source(2)    # 2 = SRCO oscillator output :contentReference[oaicite:0]{index=0}
time.sleep(2)                      # you should see a stream of pulses on the IRQ pin
# Then restore for real lightning interrupts:
sensor.set_irq_output_source(3)    # 3 = lightning (LCO) interrupts :contentReference[oaicite:1]{index=1}
print("Self-test done; IRQ set back for lightning.")
print("start lightning detect.")
'''
'''
while True:
    src = sensor.get_interrupt_src()
    if src != 0:
        print("Polled intSrc:", src)
    time.sleep(0.5)
'''
while True:
    time.sleep(1.0)




