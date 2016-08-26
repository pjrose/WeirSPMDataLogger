#!/usr/bin/env python
import os

# Return CPU temperature as a character string
def getCPUTemperature():
    res = os.popen('vcgencmd measure_temp').readline()
    temp_c = float(res.replace("temp=","").replace("'C\n",""))
    temp_f = 9.0/5.0*temp_c+32.0
    return "{0:.2f}".format(temp_c) + 'C, ' + "{0:.2f}".format(temp_f) + ' F'


print(getCPUTemperature())


