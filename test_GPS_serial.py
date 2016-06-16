#!/usr/bin/python3

#
# Simple test of GPS sensor
#

from time import sleep
from GPS_serial import GPS_AdafruitSensor

if __name__ == "__main__":
    print("Testing GPS sensor (running 5x with 5s pause)...")

    print("Initialising...")
    gps_sensor = GPS_AdafruitSensor(interface='/dev/ttyAMA0')
    sleep(2)
    #print("/dev/ttyAMA0")
    
    print('Reading 1: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    sleep(1)
    print('Reading 2: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    sleep(1)
    print('Reading 3: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    sleep(1)
    print('Reading 4: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    sleep(1)
    print('Reading 5: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    sleep(1)
    print('Reading 6: ' + gps_sensor.timestamp_str() + ' ' + gps_sensor.data_str() )
    
    print("Done.")

    # raw values - not currently implemented any differently
    # will move more fields over when correctly reading sensor
    # gpsSensor.read_sensor_raw()
