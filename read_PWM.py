#!/usr/bin/env python

# read_PWM.py
# Public Domain

import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
import threading

class reader:
   """
   A class to read oil sensor PWM signals for temperature, level and quality.
   """
   def __init__(self, pi, gpio, new_data_event):
      self.pi = pi
      self.gpio = gpio


      self.timeout_response = "{0:.2f},{1:.2f},{2:.2f}".format(-1,-1,-1)
      self.new_data_event = new_data_event

      self._SYNC = 0 
      self._OIL_TEMP = 2
      self._OIL_LEVEL = 4
      self._OIL_QUALITY = 6

      self._state = 0

      self._sync_f_ticks = 0
      self._sync_r_ticks = 0
      self._temp_r_ticks = 0
      self._temp_f_ticks = 0
      self._level_r_ticks = 0
      self._level_f_ticks = 0
      self._qual_r_ticks = 0
      self._qual_f_ticks = 0

      self._sync_low_duration = 0
      self._temp_high_duration = 0
      self._temp_low_duration = 0
      self._level_high_duration = 0
      self._level_low_duration = 0
      self._qual_high_duration = 0
      self._avg_period = 0
      self._last_tick = 0


      self._temp_c =  0
      self._temp_f = 0
      self._oil_level = 0
      self._quality = 0

          
      self._temperature_duty_cycle = 0
      self._level_duty_cycle = 0
      self._quality_duty_cycle = 0

      self._watchdog = 5000 # Milliseconds.

      pi.set_mode(gpio, pigpio.INPUT)

      self._cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._oil_sensor_callback)

   def _oil_sensor_callback(self, gpio, level, tick):
      
      if(level == 2):
         pass #watchdog timeout
      if(tick < self._last_tick or self._last_tick == 0):
         self._state = self._SYNC
      elif(level == 1 and tick - self._last_tick > 150000): #>150 ms must have been a synch pulse, avg period of other pulses is ~116ms
         self._sync_r_ticks = tick
         self._sync_low_duration = tick - self._last_tick
         #print('SYNCED, DURATION = ' + str(self._sync_low_duration))
         self._state = self._OIL_TEMP
      elif(self._state == self._OIL_TEMP and level == 0):
         self._temp_f_ticks = tick
         self._temp_high_duration = self._temp_f_ticks - self._sync_r_ticks
      elif(self._state == self._OIL_TEMP and level == 1):
         self._temp_r_ticks = tick
         self._temp_low_duration = self._temp_r_ticks - self._temp_f_ticks
         self._state = self._OIL_LEVEL
         self._temperature_duty_cycle = self._temp_high_duration / (self._temp_high_duration + self._temp_low_duration)
         #print('OIL TEMP DUTY CYCLE = ' + str(self._temp_high_duration / (self._temp_high_duration + self._temp_low_duration)))
      elif(self._state == self._OIL_LEVEL and level == 0):
         self._level_f_ticks = tick
         self._level_high_duration = self._level_f_ticks - self._temp_r_ticks
      elif(self._state == self._OIL_LEVEL and level == 1):
         self._level_r_ticks = tick
         self._level_low_duration = self._level_r_ticks - self._level_f_ticks
         self._state = self._OIL_QUALITY
         self._level_duty_cycle = self._level_high_duration / (self._level_high_duration + self._level_low_duration)
         #print('OIL LEVEL DUTY CYCLE = ' + str(self._level_high_duration / (self._level_high_duration + self._level_low_duration)))
         self._avg_period = ((self._level_high_duration + self._level_low_duration) + (self._temp_high_duration + self._temp_low_duration)) / 2
      elif(self._state == self._OIL_QUALITY and level == 0):
         self._sync_f_ticks = tick
         self._qual_high_duration = self._sync_f_ticks - self._level_r_ticks
         self._state = self._SYNC
         self._quality_duty_cycle = self._qual_high_duration / self._avg_period
         #print('OIL QUALITY DUTY CYCLE = ' + str(self._qual_high_duration / self._avg_period))

         if(self._validate_oil_sensor_readings()):
            self.new_data_event.set()
      else:
         self._state = self._SYNC
         
      self._last_tick = tick


   def _validate_oil_sensor_readings(self):
     
      self._temp_c
      self._temp_f
      self._oil_level
      self._quality
      success = False
      
      if( self._temperature_duty_cycle >= .15 <= .85 and \
          self._level_duty_cycle >= .15 <= .85 and \
          self._quality_duty_cycle >= .15 <= .85):

          self._temp_c =  (self._temperature_duty_cycle * 333.333333) -106.6666667
          self._temp_f = ((self._temp_c * 9.0) / 5.0) + 32.0
          self._oil_level = (self._level_duty_cycle * 133.333333) - 26.6666667
          self._quality =  (self._quality_duty_cycle * 8.3333) - 0.66667
        
          #print("Temperature: {0:.2f} degF, ".format(temp_f) + "Level: {0:.2f} mm, ".format(oil_level) + "Quality (1-6): {0:.2f}".format(quality))
          success = True

      self._temperature_duty_cycle = 0
      self._level_duty_cycle = 0 
      self._quality_duty_cycle = 0
      
      return success
      
   def PWM(self):
      return "{0:.2f},{1:.2f},{2:.2f}".format(self._temp_f, self._oil_level, self._quality)
      
   def cancel(self):
      """
      Cancels the reader and releases resources.
      """
      self.pi.set_watchdog(self.gpio, 0) # cancel watchdog
      self._cb.cancel()

if __name__ == "__main__":

   import time
   import pigpio
   import read_PWM
   import threading

   PWM_GPIO = 17
   RUN_TIME = 60.0
   
   print("PWM GPIO= " + str(PWM_GPIO) + ", RUN_TIME= " + str(RUN_TIME))
   
   pi = pigpio.pi()

   new_data_event = threading.Event()

   p = read_PWM.reader(pi, PWM_GPIO, new_data_event)
   
   start = time.time()

   while (time.time() - start) < RUN_TIME:
      if(new_data_event.wait(5)):
         new_data_event.clear()
         print('New data from oil sensor: ' + p.PWM())
      else:
         print('timeout')
         

   p.cancel()

   pi.stop()

