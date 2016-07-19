#!/usr/bin/python
# -*- coding: utf-8 -*-
# improved and completed by PiModules Version 1.0 29.08.2015
# picoStatus-v3.py by KTB is based on upisStatus.py by Kyriakos Naziris
# Kyriakos Naziris / University of Portsmouth / kyriakos@naziris.co.uk


import smbus
import time
import datetime

# You can install psutil using: sudo pip install psutil
#import psutil

i2c = smbus.SMBus(1)

def pwr_mode():
   data = i2c.read_byte_data(0x69, 0x00)
   data = data & ~(1 << 7)
   if (data == 1):
      return "RPi"
   elif (data == 2):
      return "BAT"
   else:
      return "ERR"

def bat_level():
   time.sleep(0.1)
   data = i2c.read_word_data(0x69, 0x01)
   data = format(data,"02x")
   return (float(data) / 100)

def rpi_level():
   time.sleep(0.1)
   data = i2c.read_word_data(0x69, 0x03)
   data = format(data,"02x")
   return (float(data) / 100)

def fw_version():
   time.sleep(0.1)
   data = i2c.read_byte_data(0x6b, 0x00)
   data = format(data,"02x")
   return data

def sot23_temp():
   time.sleep(0.1)
   data = i2c.read_byte_data(0x69, 0x0C)
   data = format(data,"02x")
   return data

def to92_temp():
   time.sleep(0.1)
   data = i2c.read_byte_data(0x69, 0x0d)
   data = format(data,"02x")
   return data

def ad1_read():
   time.sleep(0.1)
   data = i2c.read_word_data(0x69, 0x05)
   data = format(data,"02x")
   return (float(data) / 100)

def ad2_read():
   time.sleep(0.1)
   data = i2c.read_word_data(0x69, 0x07)
   data = format(data,"02x")
   return (float(data) / 100)

print " "
print "        pico status V1.0"
print "***********************************"
print " ","UPS PIco Firmware:",fw_version()
print " ","Powering Mode:",pwr_mode()
print " ","BAT Volatge:", bat_level(),"V"
print " ","RPi Voltage:" , rpi_level(),"V"
print " ","SOT23 Temperature:" , sot23_temp(),"C"
print " ","TO-92 Temperature:" , to92_temp(),"C"
print " ","A/D1 Voltage:" , ad1_read(),"V"
print " ","A/D2 Voltage:" , ad2_read(),"V"
print "***********************************"
print " "

