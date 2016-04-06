# Import the libraries to use time delays, send os commands and access GPIO pins
import RPi.GPIO as GPIO
import smbus
import time
import os

enable_sta_counter = False
toggle_val = 0

try:
    i2c = smbus.SMBus(1)
    data = i2c.read_byte_data(0x6b, 0x00)
    if(int(data) > 0):
        enable_sta_counter = True
        print 'Successfully communicated with UPS and fw ver. is ' + str(data)
except:
    pass

if(not enable_sta_counter):
    print 'Failed to communicate with UPS over i2c.'

GPIO.setmode(GPIO.BCM) # Set pin numbering to board numbering
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP) # Setup pin 27 as an input
GPIO.setup(22, GPIO.OUT) # Setup pin 22 as an output



while True: # Setup a while loop to wait for a button press
    GPIO.output(22,True)
    time.sleep(0.25) # Allow a sleep time of 0.25 second to reduce CPU usage
    GPIO.output(22,False)
    if(GPIO.input(27)==0): # Setup an if loop to run a shutdown command when button press sensed
    	os.system("sudo shutdown -h now") # Send shutdown command to os
    	break
    
    if(enable_sta_counter):
        i2c.write_byte_data(0x6b, 0x08, 10)
        
        if(toggle_val == 1) :
            toggle_val = 0
        else:
            toggle_val = 1
            
        i2c.write_byte_data(0x6b, 0x0C, toggle_val) #toggle the blue LED
    time.sleep(0.25) # Allow a sleep time of 0.25 second to reduce CPU usage

