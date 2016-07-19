#!/usr/bin/env python

import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
import os




class controller:
   """
   A class to read the temperature sensor and set the fan speed accordingly.
   """



#UPS PICO i2c fan control register reference:
      #0x6B 15 : 0 disables the fan, 1 enables it
      #0x6B 16 (0x10) : 0 is stop, 1 is 100%, 2 is 25%, 3 is 50%, 4 is 75%
      #0x69 12 (0x0C) : tempreature in C of SOT-23 in BCD (i.e. 0x36 is 36C)
      #0x69 13 (0x0D) : temperature in C of TO-92 (fan kit) in BCD (i.e. 0x36 is 36C)
      #see setup notes (or pi modules forum) to get TO-92 sensor working, it's not enabled by default!

       

   def __init__(self, pi, i2c_handle_69, i2c_handle_6b):
      self.i2c_handle_69 = i2c_handle_69
      self.i2c_handle_6b = i2c_handle_6b
      self.pi = pi
      self.fan_speed = 0
      self.fan_speed_str = 'off'
      self.pi.i2c_write_byte_data(self.i2c_handle_6b, 15, 1)

   def getCPUTemperature(self):
      temp_c = float(os.popen('vcgencmd measure_temp').readline().replace("temp=","").replace("'C\n",""))
      #temp_f = 9.0/5.0*float+32.0
      return temp_c

       
   def adjust_fan_speed(self):
    
      #when temperature reaches this many degrees C, fan will be set to the corresponding speed percent (THRESHOLD_75 is 75% corresponds to 75% speed)
      THRESHOLD_FULLSPEED = 55
      THRESHOLD_75 = 50
      THRESHOLD_50 = 45
      THRESHOLD_25 = 40

      #Register values 
      FULLSPEED = 1
      SPEED_75 = 4
      SPEED_50 = 3
      SPEED_25 = 2
      STOP = 0

      #degrees c of temperature drop required before change fan speed is reduced
      HYSTERESIS = 5

      ups_TO92_temperature = int('{:02x}'.format(self.pi.i2c_read_byte_data(self.i2c_handle_69, 13)))
      ups_SOT23_temperature = int('{:02x}'.format(self.pi.i2c_read_byte_data(self.i2c_handle_69, 12)))
      core_temperature = self.getCPUTemperature()

      if(ups_TO92_temperature == 0):
         temperature = core_temperature
      else:
         temperature = ups_TO92_temperature
                  
      new_speed = self.fan_speed
      
      if(self.fan_speed is STOP and temperature >= THRESHOLD_25): 
         if(temperature > THRESHOLD_FULLSPEED): 
            new_speed = FULLSPEED
         elif(temperature > THRESHOLD_75): 
            new_speed = SPEED_75  
         elif(temperature > THRESHOLD_50): 
            new_speed = SPEED_50 
         else:
            new_speed = SPEED_25
            
      elif(self.fan_speed is FULLSPEED and temperature <= (THRESHOLD_FULLSPEED - HYSTERESIS) ): 
            new_speed = SPEED_75
            
      elif(self.fan_speed is SPEED_75):
            if(temperature > THRESHOLD_FULLSPEED):
               new_speed = FULLSPEED
            elif(temperature <= (THRESHOLD_75 - HYSTERESIS)):
               new_speed = SPEED_50 
               
      elif(self.fan_speed is SPEED_50): 
         if(temperature > THRESHOLD_75):
            new_speed = SPEED_75
         elif(temperature <= (THRESHOLD_50 - HYSTERESIS)):
            new_speed = SPEED_25 

      elif(self.fan_speed is SPEED_25):
         if(temperature > THRESHOLD_50):
            new_speed =  SPEED_50
         elif(temperature <= (THRESHOLD_25 - HYSTERESIS)):
            new_speed = STOP

      #trap incase TO-92 sensor is not working or not setup properly, default fan to 50%
      if(temperature == 0):
         new_speed = SPEED_50
            
      if(self.fan_speed is not new_speed):
         self.fan_speed = new_speed
         self.pi.i2c_write_byte_data(self.i2c_handle_6b, 16, self.fan_speed)

      if(self.fan_speed == STOP):
         self.fan_speed_str = 'off'
      elif(self.fan_speed ==  SPEED_25):
         self.fan_speed_str = '25%'
      elif(self.fan_speed ==  SPEED_50):
         self.fan_speed_str = '50%'
      elif(self.fan_speed ==  SPEED_75):
         self.fan_speed_str = '75%'
      elif(self.fan_speed ==  FULLSPEED):
         self.fan_speed_str = '100%'     
         
      return 'Sys temps: Core ' + str(int(core_temperature)) + 'C,UPS SOT23 ' + str(ups_SOT23_temperature) + 'C, UPS TO-92 '+ str(ups_TO92_temperature) + 'C, fan speed: ' + str(self.fan_speed_str)


    
if __name__ == "__main__":

   import time
   import pigpio
   import picofan

   pi = pigpio.pi()
   
   i2c_handle_6b = pi.i2c_open(1, 0x6B) #i2c bus 1, register 0x6b
   i2c_handle_69 = pi.i2c_open(1, 0x69) #i2c bus 1, register 0x69
   
   ups = picofan.controller(pi, i2c_handle_69, i2c_handle_6b)
   
   start = time.time()

   while (time.time() - start) < 60:
      time.sleep(5)
      print(ups.adjust_fan_speed())

   pi.i2c_close(i2c_handle_6b)
   pi.i2c_close(i2c_handle_69)
   
   pi.stop()
