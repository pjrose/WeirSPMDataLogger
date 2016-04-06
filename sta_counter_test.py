import smbus

i2c = smbus.SMBus(1)
i2c.write_byte_data(0x6b, 0x08, 5)
