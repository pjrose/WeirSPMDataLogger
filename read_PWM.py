#!/usr/bin/env python

import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
import threading

class reader:
   """
   A class to read oil sensor PWM signals for temperature, level and quality.
   Modified on 2-27-2017 by PJR, was designed for a 4 pulse sensor (sync, level, temp, quality?), now only a duty cycle to denote level.
    
  Optionally a weighting may be specified.  This is a number
      between 0 and 1 and indicates how much the old reading
      affects the new reading.  It defaults to 0 which means
      the old reading has no effect.  This may be used to
      smooth the data.   
   """
   def __init__(self, pi, gpio): 
      weighting = 0
      if weighting < 0.0:
         weighting = 0.0
      elif weighting > 0.99:
         weighting = 0.99

      self._new = 1.0 - weighting # Weighting for new reading.
      self._old = weighting       # Weighting for old reading.

      self._high_tick = None
      self._period = None
      self._high = None
      self.pi = pi
      self.gpio = gpio


      self._duty_cycle = 0

      self._last_tick = 0
      self._watchdog = 5000 # Milliseconds.
      pi.set_mode(gpio, pigpio.INPUT)

      self._cb = pi.callback(gpio, pigpio.EITHER_EDGE, self._oil_sensor_callback)
      pi.set_watchdog(gpio, self._watchdog)

   def _oil_sensor_callback(self, gpio, level, tick):

      if level == 1:

         if self._high_tick is not None:
            t = pigpio.tickDiff(self._high_tick, tick)

            if self._period is not None:
               self._period = (self._old * self._period) + (self._new * t)
            else:
               self._period = t

         self._high_tick = tick

      elif level == 0:

         if self._high_tick is not None:
            t = pigpio.tickDiff(self._high_tick, tick)

            if self._high is not None:
               self._high = (self._old * self._high) + (self._new * t)
            else:
               self._high = t

      elif level == 2: #watchdog time out
        self._high = pi.read(gpio)
        self._period = 1

   def frequency(self):
      """
      Returns the PWM frequency.
      """
      if self._period is not None:
         return 1000000.0 / self._period
      else:
         return 0.0

   def pulse_width(self):
      """
      Returns the PWM pulse width in microseconds.
      """
      if self._high is not None:
         return self._high
      else:
         return 0.0

   def getUpdate(self):
         f = self.frequency()
         pw = self.pulse_width()
         dc = self.duty_cycle()
         return ",{:.2f}".format(dc)

   def getUpdate_debug(self):
         f = self.frequency()
         pw = self.pulse_width()
         dc = self.duty_cycle()
         return ", oil sensor freq= {:.3f} pulse width (usec)= {} duty cycle= {:.2f}%".format(f, int(pw+0.5), dc)


   def duty_cycle(self):
      """
      Returns the PWM duty cycle percentage.
      """
      if self._high is not None:
         return 100.0 * self._high / self._period
      else:
         return 0.0

      
   def cancel(self):
      """
      Cancels the reader and releases resources.
      """
      self.pi.set_watchdog(self.gpio, 0) # cancel watchdog
      self._cb.cancel()

if __name__ == "__main__": #debug test routine if called standalone (not from a parent program)

   import time
   import pigpio
   import read_PWM
   import threading

   PWM_GPIO = 24 #pin 18
   RUN_TIME = 60.0
   
   print("PWM GPIO= " + str(PWM_GPIO) + ", RUN_TIME= " + str(RUN_TIME))
   
   pi = pigpio.pi()

   pi.set_mode(PWM_GPIO, pigpio.INPUT)

   p = read_PWM.reader(pi, PWM_GPIO) 
   
   start = time.time()

   while (time.time() - start) < RUN_TIME:
         time.sleep(5)
         f = p.frequency()
         pw = p.pulse_width()
         dc = p.duty_cycle()
         print(p.getUpdate_debug())

   p.cancel()
   pi.stop()

