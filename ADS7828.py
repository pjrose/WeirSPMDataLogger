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
    def calc_temperature_steinhart(self, resistance):
 
        BCOEFFICIENT = 3929.63
        THERMISTORNOMINAL = 3179.24
        TEMPERATURENOMINAL = 25

        steinhart = resistance / THERMISTORNOMINAL;     # (R/Ro)
        steinhart = math.log(steinhart);                  # ln(R/Ro)
        steinhart = steinhart / BCOEFFICIENT;                   # 1/B * ln(R/Ro)
        steinhart = steinhart + (1.0 / (TEMPERATURENOMINAL + 273.15)); # + (1/To)
        steinhart = 1.0 / steinhart;                            # Invert
        steinhart = steinhart - 273.15;                         #convert from k to C
        temperature_c = round(steinhart,3)
        temperature_f = round((steinhart * (9.0/5.0)) + 32,3)
        return temperature_c, temperature_f

    def getUpdate(self):
        #thermistor and measurement interface constants
        REF_RESISTOR = 453.0  #'r2', ohms
        AD_FULLSCALE_COUNTS = 4095.0
        THERMISTOR_REF_VOLTS = 3.3
        AD_REF_VOLTS = 2.5

        #honeywell, 0.5-4.5V -> 0-300 PSI
        PRESSURE1_SCALE = 75   #slope
        PRESSURE1_OFFSET = -37.5  #y-intercept

        #honeywell, 0.5-4.5V -> 0-300 PSI
        PRESSURE2_SCALE = 75   #slope
        PRESSURE2_OFFSET = -37.5  #y-intercept

        adc_counts = self.readChannel(0) 
        ad_thermistor_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095.0
        ad_thermistor_volts = ad_thermistor_ratio * 2.5
        resistance = (REF_RESISTOR * ((1.0 / ad_thermistor_ratio) - 1.0)) * (THERMISTOR_REF_VOLTS/AD_REF_VOLTS) #solving for r1 from voltage divider calc, correct for difference in reference voltage
        temp1_c, temp1_f =  self.calc_temperature_steinhart(resistance)


        thermistor1_res_str = str(round(resistance, 1))
        thermistor1_volts_str = str(round(ad_thermistor_volts,4))
        thermistor1_temperature_str = str(round(temp1_f, 1))

        adc_counts = self.readChannel(1) 
        ad_thermistor_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095.0
        ad_thermistor_volts = ad_thermistor_ratio * 2.5
        resistance = (REF_RESISTOR * ((1.0 / ad_thermistor_ratio) - 1.0)) * (THERMISTOR_REF_VOLTS/AD_REF_VOLTS) #solving for r1 from voltage divider calc, correct for difference in reference voltage
        temp2_c, temp2_f =  self.calc_temperature_steinhart(resistance)        

        thermistor2_res_str = str(round(resistance, 1))
        thermistor2_volts_str = str(round(ad_thermistor_volts,4))
        thermistor2_temperature_str = str(round(temp2_f, 1))

        #follow this same pattern to read other channels, for example, votlage on channel 4: 
        adc_counts = self.readChannel(4)
        ad_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095
        pressure_volts = 2.5 * 2 * ad_ratio #2.5 becuase it is the reference voltage of the A/D converter. 2 becuase it is the ratio of the input voltage divider.
        pressure = (pressure_volts * PRESSURE1_SCALE) + PRESSURE1_OFFSET
        pressure1_str = str(round(pressure,1))

        adc_counts = self.readChannel(5)
        ad_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095
        pressure_volts = 2.5 * 2 * ad_ratio #2.5 becuase it is the reference voltage of the A/D converter. 2 becuase it is the ratio of the input voltage divider.
        pressure = (pressure_volts * PRESSURE2_SCALE) + PRESSURE2_OFFSET
        pressure2_str = str(round(pressure,1))

        #channels 6 and 7 are electrically connected, but not used in this version of the software. 
        #adc_counts = self.readChannel(6)
        #ad_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095
        #pressure_volts = 2.5 * 2 * ad_ratio #2.5 becuase it is the reference voltage of the A/D converter. 2 becuase it is the ratio of the input voltage divider.
        #adc_6_str = str(round(pressure_volts,4))

        #adc_counts = self.readChannel(7)
        #ad_ratio =  adc_counts / AD_FULLSCALE_COUNTS #full scale is 4095
        #pressure_volts = 2.5 * 2 * ad_ratio #2.5 becuase it is the reference voltage of the A/D converter. 2 becuase it is the ratio of the input voltage divider.
        #adc_7_str = str(round(pressure_volts,4))


        return ',' + pressure1_str  + ',' + pressure2_str + ',' + thermistor1_temperature_str + ',' +  thermistor2_temperature_str

if __name__ == "__main__": #debug test routine if called standalone (not from a parent program)

   import time
   import pigpio
   import threading

   pi = pigpio.pi()
   i2c_handle = pi.i2c_open(1, 0x48) #bus id is always 1, default addres is 0x48.

   adc = ADS7828(pi, i2c_handle)

   while True:
      print(adc.getUpdate())
      time.sleep(3)
    
   p.cancel()
   pi.stop()









    