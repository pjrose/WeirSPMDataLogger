import pigpio

#used to check the analog input functionality on the UPS Pico
pi = pigpio.pi()
i2c_handle = pi.i2c_open(1, 0x69)
try:
    
    ad1_volts = float(format(pi.i2c_read_word_data(i2c_handle, 0x05),"02x")) / 100.0
    print('ad1_volts = ' + str(ad1_volts) + ' volts')
    ad2_volts = float(format(pi.i2c_read_word_data(i2c_handle, 0x07),"02x")) / 100.0
    print('ad2_volts = ' + str(ad2_volts) + ' volts')
finally:
    pi.i2c_close(i2c_handle)
    pi.stop()
