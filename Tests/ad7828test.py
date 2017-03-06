import smbus
import math
import time

class ADS7828:

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


    def __init__(self, address=0x48, busId=1, debug=False):
        self.i2c = smbus.SMBus(busId)
        self.address = address
        self.debug = debug

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

        data = self.i2c.read_i2c_block_data(self. address, config, 2)
        return  2.5 * ( ((data[0] << 8) + data[1]) / 4095.0 )

    def getUpdate(self):
        print("---------------------------------")
        print("ch0: " + str(round(self.readChannel(0),3)) + " volts")
        print("ch1: " + str(round(self.readChannel(1),3)) + " volts")
        print("ch4: " + str(round(2.0 * self.readChannel(4),3)) + " volts") #x2 becuase of input voltage divider.
        print("ch5: " + str(round(2.0 * self.readChannel(5),3)) + " volts")
        print("ch6: " + str(round(2.0 * self.readChannel(6),3)) + " volts")
        print("ch7: " + str(round(2.0 * self.readChannel(7),3)) + " volts")
        

adc = ADS7828(0x48, 1, True)
while True:
    adc.getUpdate()
    time.sleep(3)





    