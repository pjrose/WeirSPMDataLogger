#!/usr/bin/python

#
# FishPi - An autonomous drop in the ocean
#
# Adafruit GPS module:
#  - http://www.adafruit.com/products/746
#  - http://learn.adafruit.com/adafruit-ultimate-gps/overview
#  - based on Arduino library at https://github.com/adafruit/Adafruit-GPS-Library
#
#  - nmea sentence details at http://aprs.gids.nl/nmea/
#
#  - Standard sense gives:
#    - fix, lat, lon, heading, speed, altitude, num_sat, timestamp, datestamp
#
#  - Detailed raw sense gives:
#    - fix, lat, lon, heading, speed, altitude, num_sat, timestamp, datestamp

from datetime import datetime
import serial
import logging, traceback
import threading

class GPS_AdafruitSensor:
    """ GPS Navigatron over serial port. """

    # different commands to set the update rate from once a second (1 Hz) to 10 times a second (10Hz)
    PMTK_SET_NMEA_UPDATE_1HZ = b'$PMTK220,1000*1F'
    PMTK_SET_NMEA_UPDATE_5HZ = b'$PMTK220,200*2C'
    PMTK_SET_NMEA_UPDATE_10HZ = b'$PMTK220,100*2F'

    # baud rates
    PMTK_SET_BAUD_57600 = b'$PMTK250,1,0,57600*2C'
    PMTK_SET_BAUD_9600 = b'$PMTK250,1,0,9600*17'

    # turn on only the second sentence (GPRMC)
    PMTK_SET_NMEA_OUTPUT_RMCONLY = b'$PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*29'
    # turn on GPRMC and GGA
    PMTK_SET_NMEA_OUTPUT_RMCGGA = b'$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28'
    # turn on GPRMC, GPVTG and GGA
    PMTK_SET_NMEA_OUTPUT_RMCVTGGGA = b'$PMTK314,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*29'
    #turn on ALL THE DATA
    PMTK_SET_NMEA_OUTPUT_ALLDATA = b'$PMTK314,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0*28'
    #turn off output
    PMTK_SET_NMEA_OUTPUT_OFF = b'$PMTK314,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28'

    # ask for the release and version
    PMTK_Q_RELEASE = b'$PMTK605*31'

    #  how long to wait when we're looking for a response
    MAXWAITSENTENCE = 5

    def __init__(self, interface="", hw_interface="/dev/ttyAMA0", baud=9600, debug=False):
        self.debug = debug
        self._GPS = serial.Serial(hw_interface, baud)
        self._GPS.write(self.PMTK_SET_NMEA_UPDATE_1HZ)
        self._GPS.write(self.PMTK_SET_BAUD_9600)
        self._GPS.write(self.PMTK_SET_NMEA_OUTPUT_RMCVTGGGA)
        self.timestamp = datetime(2000,1,1)
        self.alt = 0
        self.lat = 0
        self.lon = 0
        self._GPS.flush()
        self.thread = threading.Thread(target=self.wait_for_sentence, name='gps serial com')
        self.thread.setDaemon(True)
        self.thread.start()

    def data_str(self):
        return ',{0:.3f}'.format(self.lat) + ',{0:.3f}'.format(self.lon) + ',{0:.2f}'.format(self.alt)

    def timestamp_str(self):
        return self.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
         
    def wait_for_sentence(self):
        while (True):
            try:
                line = self._GPS.readline().decode('utf-8')
                if line.startswith('$GPRMC'):
                    if self.debug: print("Received GPRMC: "+line)
                    self.decode_rmc(line)
                if line.startswith('$GPGGA'):
                    if self.debug: print("Received GPGGA: "+line)
                    self.decode_gga(line)
                else:
                    continue
            except UnicodeDecodeError:
                continue
            except serial.serialutil.SerialException:
                logging.error('gps serial port exception: ' + traceback.format_exc())
                self._GPS.close()
                sleep(2)
                self._GPS.open()
                continue
                

    def zero_response(self):
        dt = datetime(2010,1,1)
        return 0,0,0,dt.time(),dt.date()

    def read_sensor_raw(self):
        """ Read raw sensor values. """
        return self.read_sensor()

    def decode_rmc(self, da_str):
        da = da_str.split(',') 
        gps_gga = dict()       
        if (da[0]=='$GPRMC' and len(da)>=12):
   
            if(str(da[3][0:2]) is ''):               
                self.lat = 0
            else:
                gps_gga['lat_deg']=int(da[3][0:2])+(float(da[3][2:])/60)
                gps_gga['ns']=da[4]
                self.lat = float(gps_gga['lat_deg']) * (1.0 if gps_gga['ns'] == 'N' else -1.0)

            if(str(da[5][0:3]) is ''):
                 self.lon = 0
            else:
                gps_gga['lon_deg']=int(da[5][0:3])+(float(da[5][3:])/60)
                gps_gga['ew']=da[6]
                self.lon = float(gps_gga['lon_deg']) * (1.0 if gps_gga['ew'] == 'E' else -1.0)
        
            gps_gga['date']='20'+da[9][4:]+'-'+da[9][2:4]+'-'+da[9][0:2]
            gps_gga['utc_time']= da[1][0:2]+':'+da[1][2:4]+':'+da[1][4:6]
            self.timestamp = datetime.strptime(gps_gga['date'] + ' ' + gps_gga['utc_time'], "%Y-%m-%d %H:%M:%S")

            #unused data...
            #gps_gga['lat_dm']=da[3][0:2]+' '+da[3][2:]
            #gps_gga['status']=da[2]
            #gps_gga['lon_dm']=da[5][0:3]+' '+da[5][3:]
            #gps_gga['speed_knot']=da[7]
            #gps_gga['speed_km']=float(da[7])*1.852
            #gps_gga['course']=da[8]
            #gps_gga['mode']=da[10]
            #gps_gga['csum']=da[11]
            

    def decode_gga(self, da_str):
        da = da_str.split(',')
        gps_gga = dict()
        
        if (da[0]=='$GPGGA' and len(da)>=15):
        
            gps_gga['msl_alt']=da[9]
            if(gps_gga['msl_alt'] is ''): gps_gga['msl_alt'] = '0'
            self.alt = float(gps_gga['msl_alt'])

            #unused data...
            #gps_gga['utc_time']= da[1][0:2]+':'+da[1][2:4]+':'+da[1][4:]
            #gps_gga['lat_deg']=int(da[2][0:2])+(float(da[2][2:])/60)
            #gps_gga['lat_dm']=da[2][0:2]+' '+da[2][2:]
            #gps_gga['ns']=da[3]
            #gps_gga['lon_deg']=int(da[4][0:3])+(float(da[4][3:])/60)
            #gps_gga['lon_dm']=da[4][0:3]+' '+da[4][3:]
            #gps_gga['ew']=da[5]
            #gps_gga['pfi']=da[6]
            #gps_gga['sat_used']=da[7]
            #gps_gga['hdop']=da[8]
            #gps_gga['msl_alt']=da[9]
            #gps_gga['alt_unit']=da[10]
            #gps_gga['geoid_sep']=da[11]
            #gps_gga['sep_unit']=da[12]
            #gps_gga['age_diff_cor']=da[13]
            #gps_gga['diff_ref_sta_id']=da[14][0:4]
            #gps_gga['csum']=da[14][4:]
