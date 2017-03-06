#!/usr/bin/env python

import time
import math
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
import threading

class ADS7828:
    """
    A class to read analog values from ad7828 on the i2c bus.
    """
    # Config Register
    __ADS7828_CONFIG_SD_DIFFERENTIAL      = 0b00000000
    __ADS7828_CONFIG_SD_SINGLE            = 0b10000000
    __ADS7828_CONFIG_CS_CH0               = 0b00000000
    __ADS7828_CONFIG_CS_CH2               = 0b00010000
    __ADS7828_CONFIG_CS_CH4               = 0b00100000
    __ADS7828_CONFIG_CS_CH6               = 0b00110000
    __ADS7828_CONFIG_CS_CH1               = 0b01000000
    __ADS7828_CONFIG_CS_CH3               = 0b01010000
    __ADS7828_CONFIG_CS_CH5               = 0b01100000
    __ADS7828_CONFIG_CS_CH7               = 0b01110000
    __ADS7828_CONFIG_PD_OFF               = 0b00000000
    __ADS7828_CONFIG_PD_REFOFF_ADON       = 0b00000100
    __ADS7828_CONFIG_PD_REFON_ADOFF       = 0b00001000
    __ADS7828_CONFIG_PD_REFON_ADON        = 0b00001100

    def __init__(self, pi, i2c_handle):
    
        self.pi = pi
        self.handle = i2c_handle

    def readChannel(self, ch):
            config = 0
            config |= self.__ADS7828_CONFIG_SD_SINGLE
            config |= self.__ADS7828_CONFIG_PD_REFON_ADON

            if ch == 0:
                config |= self.__ADS7828_CONFIG_CS_CH0
            elif ch == 1:
                config |= self.__ADS7828_CONFIG_CS_CH1
            elif ch == 2:
                config |= self.__ADS7828_CONFIG_CS_CH2
            elif ch == 3:
                config |= self.__ADS7828_CONFIG_CS_CH3
            elif ch == 4:
                config |= self.__ADS7828_CONFIG_CS_CH4
            elif ch == 5:
                config |= self.__ADS7828_CONFIG_CS_CH5
            elif ch == 6:
                config |= self.__ADS7828_CONFIG_CS_CH6
            elif ch == 7:
                config |= self.__ADS7828_CONFIG_CS_CH7

            (b, d) = self.pi.i2c_read_i2c_block_data(self.handle, config, 2)
            if b >= 0:
                return  ((d[0] << 8) + d[1])
            else:
                print("AD ERROR CODE: " + str(b))
                return 0


    def getUpdate(self):
        #thermistor and measurement interface constants
        REF_RESISTOR = 453.0  #'r2', ohms
        AD_FULLSCALE_COUNTS = 4095.0
        AD_REF_VOLTS = 2.5
        THERMISTOR_REF_VOLTS = 3.3
        THERMISTORNOMINAL = 3611.75
        BCOEFFICIENT = 5138.02
        TEMPERATURENOMINAL = 25

        adc_counts = self.readChannel(0) 
        print("thermistor ad counts: " + str(adc_counts))  

        ad_thermistor_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095.0
        ad_thermistor_volts = ad_thermistor_ratio * 2.5
        #print("ad volts: " + str(ad_volts))

        resistance = (REF_RESISTOR * ((1.0 / ad_thermistor_ratio) - 1.0)) * (THERMISTOR_REF_VOLTS/AD_REF_VOLTS) #solving for r1 from voltage divider calc, correct for difference in reference voltage
      
        #print("Thermistor resistance: " + str(resistance))

        steinhart = resistance / THERMISTORNOMINAL;     # (R/Ro)
        steinhart = math.log(steinhart);                  # ln(R/Ro)
        steinhart = steinhart / BCOEFFICIENT;                   # 1/B * ln(R/Ro)
        steinhart = steinhart + (1.0 / (TEMPERATURENOMINAL + 273.15)); # + (1/To)
        steinhart = 1.0 / steinhart;                            # Invert
        steinhart = steinhart - 273.15;                         #convert from k to C
        temperature_c = round(steinhart,3)

        temperature_f = round((steinhart * (9.0/5.0)) + 32,3)
 
        #print("Temperature : " + str(round(steinhart,3)) + " *C, " +  str(round((steinhart * (9.0/5.0)) + 32 ,3)) + " *F")


        #follow this same pattern to read other channels, for example, votlage on channel 4: 
        adc_counts = self.readChannel(4)
        print("Pressure AD counts: " + str(adc_counts))
        ad_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095
        pressure_volts = 2.5 * 2 * ad_ratio #2.5 becuase it is the reference voltage of the A/D converter. 2 becuase it is the ratio of the input voltage divider.
        #print("ch4: " + str(round(pressure_volts,3)) + " volts")
        return str(round(ad_thermistor_volts,4)) + ',' + str(round(resistance,1)) + ','+ str(round(pressure_volts,4))

if __name__ == "__main__": #debug test routine if called standalone (not from a parent program)

   import time
   import pigpio
   import ad7828test_pigpio
   import threading

   pi = pigpio.pi()
   i2c_handle = pi.i2c_open(1, 0x48) #bus id is always 1, default addres is 0x48.

   adc = ADS7828(pi, i2c_handle)

   while True:
      print(adc.getUpdate())
      time.sleep(3)
    
   p.cancel()
   pi.stop()









    
