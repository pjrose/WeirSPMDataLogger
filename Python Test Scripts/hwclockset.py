import os
import time, datetime

def setCenturyAndReboot():
    print('setCenturyAndReboot - Attempting to set hwclock to current century, then rebooting in order to reinitialize gpsd time estimation.')
    os.system('sudo mount -o remount,rw /')
    os.system('sudo date -s 2014-01-01') #setting the system time to anything in the current century will get the gpsd to work out the time, but keep it less than 2016 so it still fails the validity check
    os.system('sudo hwclock -w') #set hwclock from updated system clock    
    print('setCenturyAndReboot - done setting current century, running reboot command...')
    os.system('sudo reboot -f')    

def setHWClock(): #gps time is expected to be YYYY-MM-DDTHH:MM:SS.000Z format.
    #DOES NOT WORK YET, INVESTIGATING SUBPROCESS MODULE IMPLEMENTATION
    print('setHWClock - Attempting to set hwclock to current gpst time, remounting root in rw.')
    os.system('sudo mount -o remount,rw /')
    os.system('sudo date -s ' + datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
    os.system('sudo hwclock -w') #set hwclock from updated system clock
    time.sleep(5)
    os.system('sudo mount -o remount,ro /')
    print('setHWClock - done setting clock, remounted root as ro.')
