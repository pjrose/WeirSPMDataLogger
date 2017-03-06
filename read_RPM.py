#!/usr/bin/env python

# read_RPM.py
# Public Domain

import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html

class reader:
   """
   A class to read speedometer pulses and calculate the RPM.
   """
   def __init__(self, pi, gpio, pulses_per_rev=1.0, weighting=0.5, min_RPM=5.0, max_RPM=1000):
      """
      Instantiate with the Pi and gpio of the RPM signal
      to monitor.

      Optionally the number of pulses for a complete revolution
      may be specified.  It defaults to 1.

      Optionally a weighting may be specified.  This is a number
      between 0 and 1 and indicates how much the old reading
      affects the new reading.  It defaults to 0 which means
      the old reading has no effect.  This may be used to
      smooth the data.

      Optionally the minimum RPM may be specified.  This is a
      number between 1 and 1000.  It defaults to 5.  An RPM
      less than the minimum RPM returns 0.0.
      """
      self.pi = pi
      self.gpio = gpio
      self.pulses_per_rev = pulses_per_rev

 

      if min_RPM > 1000.0:
         min_RPM = 1000.0
      elif min_RPM < 1.0:
         min_RPM = 1.0

      if max_RPM > 100000.0:
         max_RPM = 100000.0
      elif max_RPM < 1.0:
         max_RPM = 1.0

      self.min_RPM = min_RPM

      self.max_RPM = max_RPM

      self._min_period = 1000000.0 * (1.0/ ( (float(pulses_per_rev)) * (float(max_RPM) / 60.0))) #microseconds

      self._watchdog = 60000/min_RPM # Milliseconds

      if weighting < 0.0:
         weighting = 0.0
      elif weighting > 0.99:
         weighting = 0.99

      self._new = 1.0 - weighting # Weighting for new reading.
      self._old = weighting       # Weighting for old reading.

      self._high_tick = None
      self._period = None

      pi.set_mode(gpio, pigpio.INPUT)
      pi.set_pull_up_down(gpio, pigpio.PUD_UP)
      self._cb = pi.callback(gpio, pigpio.RISING_EDGE, self._cbf)
      pi.set_watchdog(gpio, self._watchdog)

   def _cbf(self, gpio, level, tick):

      

      if level == 1: # Rising edge.

         if self._high_tick is not None and tick > self._high_tick:
            t = pigpio.tickDiff(self._high_tick, tick) #microseconds
            #print('duration = ' + str(t))
            #print('min period = ' + str(self._min_period))
            

            if(t >= self._min_period):
               if self._period is not None:
                  self._period = (self._old * self._period) + (self._new * t)
               else:
                  self._period = t

         self._high_tick = tick

      elif level == 2: # Watchdog timeout.

         if self._period is not None:
            if self._period < 2000000000:
               self._period += (self._watchdog * 1000)

   def getUpdate(self):
      """
      Returns the RPM.
      """
      RPM = 0.0
      #print("period= " + str(self._period))
      if self._period is not None:
         RPM = 60000000.0 / (self._period * self.pulses_per_rev)
         if RPM < self.min_RPM:
            RPM = 0.0

      return ",{0:.2f}".format(RPM)

   def cancel(self):
      """
      Cancels the reader and releases resources.
      """
      self.pi.set_watchdog(self.gpio, 0) # cancel watchdog
      self._cb.cancel()

if __name__ == "__main__":

   import time
   import pigpio
   import read_RPM

   RPM_GPIO = 17
   RUN_TIME = 60.0
   SAMPLE_TIME = 2.0
   
   print("RPM GPIO= " + str(RPM_GPIO) + ", RUN_TIME= " + str(RUN_TIME) + ", SAMPLE_TIME= " + str(SAMPLE_TIME))


   
   pi = pigpio.pi()

   p = read_RPM.reader(pi, RPM_GPIO)

   print("min period " + str(p._min_period))
   
   start = time.time()

   while (time.time() - start) < RUN_TIME:

      time.sleep(SAMPLE_TIME)

      RPMstr = p.getUpdate()
     
      print('RPM= ' + RPMstr)

   p.cancel()

   pi.stop()


