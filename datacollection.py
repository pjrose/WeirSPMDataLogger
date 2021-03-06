#!/usr/bin/python3
# vim: ts=4 sts=4 sw=4 ft=python expandtab :

"""
datacollection.py; Copyright (C) 2016 Foresight Automation  
Watchdog code: Copyright (C) 2015 D.S. Ljungmark, Modio AB  

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import pigpio, read_RPM, read_PWM, picofan, ADS7828
import os, subprocess, sys, signal, inspect, platform, traceback
import serial,  serial.tools.list_ports #see https://learn.adafruit.com/arduino-lesson-17-email-sending-movement-detector/installing-python-and-pyserial for install instructions on windows
import sqlite3
import time, datetime
import socket
import threading, queue
import requests
import logging, logging.handlers
from GPS_serial import GPS_AdafruitSensor

   
def acquire_data(main_queue, killer, pi, i2c_handle_6b, i2c_handle_69, i2c_handle_ADS7828, reporting_interval): #new_data_event):
    #target data string:
    #timestamp           ,lat,  ,lon     ,el    ,press , temp , level, qual,rpm
    #2016-03-16T16:15:04Z,32.758,-97.448,199.700,32.808,63.722,26.887,2.144,0.000
   
        
    PWM_GPIO = 24 # to pin 18 on pi, mistakenly labeled "5" on rev c of the interface PCB
    RPM_GPIO = 17 # to pin 11 on the pi. 

    #for reference, the ups uses gpio 27 (pin 13) to shutdown the pi (FSSD) and 22 (pin 15) is use for pulse train output to the ups (watchdog), 4 is used by the GPS PPS output, STACounter enable on 25 (pin 22)

    led_state = 0
    
    analog_sensors = ADS7828.ADS7828(pi, i2c_handle_ADS7828)
    oil_sensor = read_PWM.reader(pi, PWM_GPIO)
    rpm_sensor = read_RPM.reader(pi, RPM_GPIO)

    UPS_Pico_run_prior = 0 
    UPS_Pico_run_temp = 0
    UPS_Pico_run_read_count = 0
    UPS_Pico_run_read_errors = 0
    UPS_PICO_RUN_MAX_READ_ERRORS = 5
    
    if(reporting_interval == 0):
       reporting_interval = 5
    gps_sensor = GPS_AdafruitSensor(interface='/dev/ttyAMA0')
    time_format_str = '%Y-%m-%dT%H:%M:%SZ'
    system_clock_set_from_gps = False
    

    while not killer.kill_now:
        try:
            logging.debug('acquire_data process launched...')

            while not killer.kill_now:


                #---------verifying that the Pico UPS is running properly ------------- 
                UPS_Pico_run_now = pi.i2c_read_word_data(i2c_handle_69, 0x0e) #rolling vale, should change after each read.

                if(UPS_Pico_run_now == UPS_Pico_run_prior):
                    UPS_Pico_run_read_errors += 1
                    if(UPS_Pico_run_read_errors >= UPS_PICO_RUN_MAX_READ_ERRORS):
                        raise TimeoutError('The UPS Pico_run register (UPS Pico module status register 69 0x0E) has returend the same value (' + str(UPS_Pico_run_now) + ') ' + str(UPS_Pico_run_read_errors) + ' times, which most likely indicates that the UPS is not running (either shutdown or locked up). The number of successful reads prior to error: ' + str(UPS_Pico_run_read_count))
                else:
                    UPS_Pico_run_read_errors = 0
                    UPS_Pico_run_read_count += 1
                UPS_Pico_run_prior = UPS_Pico_run_now

            
                time.sleep(reporting_interval)

                #---------begin data colection ------------- 
                timestamp = gps_sensor.timestamp
                timestamp_str = timestamp.strftime(time_format_str) 

                pressure_str = analog_sensors.getUpdate()
                oil_str = oil_sensor.getUpdate()
                rpm_str = rpm_sensor.getUpdate()

                #---------concatenating, checking minimum number of fields and date validity ------------- 
                # all of the fields have leading commas.
                data_str = timestamp_str + gps_sensor.data_str() + pressure_str + oil_str + rpm_str
                    
                
                if(len(data_str.split(',')) < 10):
                    logging.debug('Invalid data length, < 10 after split on comma, ACTUAL DATA: ' + data)
                    continue
                if(timestamp.year < 2016):
                    logging.debug('Discarding sample with an invalid timestamp: ' + timestamp_str)
                    continue
                else:
                    if not system_clock_set_from_gps: #only done once at startup
                        logging.debug('Setting date according to GPS')
                        os.system('sudo date -s ' + timestamp_str)
                        system_clock_set_from_gps = True

                filename = gps_sensor.timestamp.strftime("%Y-%m-%d_%H.csv") #change log file every hour
                main_queue.put(('new data', filename, data_str))
                # print(data_str)
                led_state = 1 - led_state
                pi.i2c_write_byte_data(i2c_handle_6b, 0x0D, led_state) #toggle the red LED to show data is being processed
                    

        except Exception as ex:
            logging.error('acquire_data: ' + traceback.format_exc())
            main_queue.put(('quit',))
        finally:
            logging.debug('DAQ thread caught stop signal.')
            try:
                pi.i2c_write_byte_data(i2c_handle_6b, 0x0D, 0) #turn off the red LED
                r.cancel() #stop the call backs            
                p.cancel()
            except:
                pass
            main_queue.put(('DAQ thread stopped',))
            logging.debug('DAQ thread is exiting.')
    
def keyword_args_to_dict(**kwargs):
    return {k: v for (k,v) in kwargs.items() if v != None}

def upload_data_to_thingspeak(upload_queue, main_queue, db_file_path, killer):
    
    #**********thingspeak configuration*************#
    NUMOFCHANNELS = 6
    url = 'https://api.thingspeak.com/update'
    field_keys = ['field' + str(n) for n in range(1,NUMOFCHANNELS+1)]
    headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
    #write_key =  'ZHHHO6RTJOAHCAYW'#<--FAI's 'WeirTest' channel
    #write_key =  'ODZXE1UNTM1825OX' #<--TREVER'S TEST CHANNEL
    write_key =  'BNUIKOFOWYPRJ80I' #<--
    post_interval = 15 #seconds between https posts attempts, thingspeak rate limit is 15 seconds

    api_keys = {'key':write_key}
    
    time_of_last_post_attempt = time.time() - post_interval
    session = requests.Session() #allows us to use connection pooling and keepalive as long as an internet connection is available.
    session.headers.update(headers)
    
    try:
        logging.debug('Upload_data_to_thingspeak process launched...')
        queue_timeouts = 0
        
        while True:
            
            if(queue_timeouts == 0 and upload_queue.empty()): #this will evel true just after all datapoints in the queue have been processed, or at startup.
                main_queue.put(('set ready_to_upload',))
            try:    
                msg = upload_queue.get(block=True, timeout=1)
            except queue.Empty:
                queue_timeouts = queue_timeouts + 1  #program will shutdown if no data sent to upload for 2 minutes
                if(queue_timeouts < 120):
                    continue
                else:
                    raise
            finally:
                if(stopping_upload_thread):
                    logging.debug('Upload process caught stop signal')
                    break

            queue_timeouts = 0 #no timeout, so reset the counter here.
            
            row_id = msg[0]
            field_values = msg[1].split(',')
            
            seconds_since_last_post = time.time() - time_of_last_post_attempt
                
            if(seconds_since_last_post < post_interval):
                seconds_to_sleep = post_interval - seconds_since_last_post

                time.sleep(seconds_to_sleep)
       
            logging.debug(str(upload_queue.qsize()) + ' items left in upload queue')
            upload_success =  False
            try:
                data = dict(zip(field_keys, [field_values[4], field_values[5], field_values[6], field_values[7],field_values[8], field_values[9]]))
                optional_args = keyword_args_to_dict(created_at = field_values[0], lat=field_values[1], long=field_values[2], elevation=field_values[3])
                params = dict(data.items() |  api_keys.items() | optional_args.items())
                thingspeak_reply = session.post(url, params, timeout = 6.1)
                upload_success = thingspeak_reply is not None and thingspeak_reply.text.isdigit() and int(thingspeak_reply.text) > 0
                logging.info('Attempted to post a datapoint with id ' + str(row_id) + ' and timestamp ' +  field_values[0] + ', reply from thingspeak: ' + thingspeak_reply.text)
            except(requests.exceptions.ConnectionError):
                logging.error("requests.exceptions.ConnectionError caught")
                continue
            except(requests.packages.urllib3.exceptions.MaxRetryError):
                logging.error("requests.packages.urllib3.exceptions.MaxRetryError caught")
                continue
            except:
                raise 
         
            time_of_last_post_attempt = time.time()
                
            if(upload_success): main_queue.put(('sent',row_id), block=False)
    except: 
        logging.error('upload data to thingspeak : ' + traceback.format_exc())
        main_queue.put(('quit',), block=False) 
        return
    finally:
        main_queue.put(('upload thread stopped',), block=False) 
        logging.info('Upload process is exiting and has sent a notification to the main thread...')

def get_CSV_Folder_Path():
    script_filename = inspect.getframeinfo(inspect.currentframe()).filename
    script_path = '/media/usb0'
    directory = os.path.join(script_path, "CSV_Files")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def get_Event_Log_Folder_Path():
    script_filename = inspect.getframeinfo(inspect.currentframe()).filename
    script_path = '/media/usb0'
    directory = os.path.join(script_path, "Eventlogs")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def get_Database_File_Path():
    script_filename = inspect.getframeinfo(inspect.currentframe()).filename
    script_path = '/media/usb0'    
    directory = os.path.join(script_path, "Database")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return os.path.join(directory, 'db.sqlite')


def init_db():
    logging.info('Initializing database...')
    db_file_path = get_Database_File_Path()
    conn = sqlite3.connect(db_file_path)
    logging.info('Running integrity check')
    for row in conn.execute('''PRAGMA integrity_check''').fetchall():
        logging.info('Result:' + str(row))
        if('ok' not in str(row[0])):
            logging.warning('Integrity check failed, deleting and recreating database file')
            conn.close()
            os.remove(db_file_path)
            conn = sqlite3.connect(db_file_path)
            break
    with conn:
        c = conn.cursor()
        c.execute('''create table if not exists datapoints (id INTEGER PRIMARY KEY, datapoint TEXT)''')
    conn.close()

    logging.info('Database initialized.')
    return db_file_path

def init_logger():
    logger = logging.getLogger()

    if(logger.handlers is None or len(logger.handlers) == 0): #don't want to register handlers more than once
        logger.setLevel(logging.NOTSET)

        #create console handler and set level to info
        handler = logging.StreamHandler()
        handler.setLevel(logging.NOTSET)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.debug('stdout logging initialized')
        
        #create rotating file handler and set level to error
        EVENT_LOG_PATH = os.path.join(get_Event_Log_Folder_Path(), 'log.out')
        handler = logging.handlers.RotatingFileHandler(EVENT_LOG_PATH, maxBytes = 1048576, backupCount = 4) #keep last 5 MB of logs in 1 MB files
        handler.setLevel(logging.NOTSET)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.debug('USB logging initialized')


class Killer:
  kill_now = False
  def __init__(self):
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, self.exit)
        
  def kill_self(self):
      if(not self.kill_now):
          logging.debug('Shutdown request variable set from within this program, attempting to shutdown nicely...')
          self.kill_now = True

  def exit(self,signum, frame):
    logging.debug('An OS kill signal was caught, attempting to shutdown nicely...')
    self.kill_now = True


def mainloop(notify, killer):
    """
    notify parameter is the systemd socket for watchdog and status
    """
    systemd_status(*notify,
                   status="Mainloop started")

    conn = None
    toggle_val = 1 #opposite of the toggle_val in acquire data so it blue and red LED's will alternately light up
    b = None
    try:
        global stopping_upload_thread #written in main, read in upload function
        pi = connectPiGPIO()
        STACounterEnabled = True
        
       
        pi.set_pull_up_down(16, pigpio.PUD_UP) #pin 36, set to pull up by default so a jumper to the ground on adjacent pin 34 means disable watchdog.
        i2c_handle_6b, i2c_handle_69, i2c_handle_ADS7828 = open_UPS_i2C_handles(pi)
        
        if(pi.read(16) == 0):
            logging.info('STACounter jumper (GPIO 16 to GND) is installed, watchdog is disabled.')
            pi.i2c_write_byte_data(i2c_handle_6b, 0x08, 0xff) #writing 0xff disables the counter.
            STACounterEnabled = False
        else:
            logging.info('STACounter jumper (GPIO 16 to GND) is NOT installed, watchdog is enabled.')
            pi.i2c_write_byte_data(i2c_handle_6b, 0x08, 180)
        


        pico_fan = picofan.controller(pi, i2c_handle_69, i2c_handle_6b)
                
        previous_filepath = current_log_filepath = None 
        
        upload_queue = queue.Queue(100)
        main_queue = queue.Queue(1000)

        db_file_path = init_db()
        
        conn = sqlite3.connect(db_file_path)
                                
        base_log_directory = get_CSV_Folder_Path()

        
        logging.info('Launching data acquisition and upload threads...')        
        
        a = threading.Thread(target=upload_data_to_thingspeak, args=(upload_queue, main_queue, db_file_path, killer))
        a.daemon = True
        a.start()
        upload_thread_running = True

        reporting_interval_seconds =  5 #seconds
        b = threading.Thread(target=acquire_data, args=(main_queue, killer, pi, i2c_handle_6b, i2c_handle_69, i2c_handle_ADS7828, reporting_interval_seconds))
        b.daemon = True
        b.start()
        daq_thread_running = True

    
        update_period = 60 #seconds between new data points
    
        last_insert = time.time() -  update_period; #so that we will always try to post on first call
        db_empty = False #assume there might be some data left in the DB
        ready_to_upload = False
        stopping_upload_thread = False
        
        while (upload_thread_running or not main_queue.empty()): #ensures that all messages have been processed before we shutdown
                if(upload_thread_running and not stopping_upload_thread and main_queue.empty() and killer.kill_now): #we need this because if the main queue is not empty, some database deletes may be pending, which will cause them to get sent twice.
                    logging.debug('Main thread caught stop signal...')
                    upload_queue.put(('stop',)) #put anything on the upload_queue incase it's waiting, then it will poll the stop variable.
                    stopping_upload_thread = True #this global variable/flag should stop the upload thread next time it dequeues any message, which will send back a 'upload thread stopped' message to this loop

                message = main_queue.get(block=True, timeout=60) #application should quit if no messages are processed for 60 seconds
                watchdog_ping(*notify)
                command = message[0]
                
                if (not stopping_upload_thread and command == 'new data'):
                    
                    #1. write the data into the csv file:                            

                    current_log_filepath = os.path.join(base_log_directory, message[1]) #generated by acquisition loop
                            
                    if not os.path.exists(base_log_directory):
                        os.makedirs(logDirectory)
                        
                    with open(current_log_filepath,"a") as out_file: #'a' means open or create file with write access to append
                        print(message[2], file=out_file)
                        
                    if current_log_filepath != previous_filepath: #file path changed
                        logging.info('Log file path is: ' + current_log_filepath) #signals to upload thread that data is transfer files, sends the current file through the queue so it gets ignored.
                        
                        
                    previous_filepath = current_log_filepath
                            
                    #2. Insert data into the database:

                    if(time.time() - last_insert >= update_period):
                        logging.info(pico_fan.adjust_fan_speed())
                        logging.debug('Inserting data to be uploaded, main_queue size ' + str(main_queue.qsize()))
                        last_insert = time.time()
                        c = conn.cursor()
                        c.execute('''INSERT INTO datapoints (datapoint) VALUES (?)''', (message[2],))
                        db_empty = False
                        conn.commit()
                        
                    #3. Check if the upload queue is ready to send more data:
                        #the following 'if' checks that the upload thread has sent it's ready signal (set ready_to_upload),
                        #and checks a flag indicating that the database possibly has data waiting to be sent, and there are no pending deletes (main_queue.empty())

                    if(ready_to_upload and not db_empty and main_queue.empty()): 
                       
                        c.execute('''SELECT * FROM datapoints ORDER BY id DESC LIMIT 3''')

                        #only send most recent 3 datapoints at a time (id PK auto increments as data is added).
                        #mainly becuase thingspeak only lets us update every 15 seconds, and new data will be inserted, queued up and posted once a minute
                        #This way, if we have a large backlog we will still post the most recent data  as it rolls in but slowly work through the backlog as time allows

                        results = c.fetchall()
                        if(results):
                            count = 0
                            for data in results:
                                count += 1
                                upload_queue.put(data)
                            ready_to_upload = False #reset ready signal, will get set when the upload queue has finished with this chunk of results
                            logging.debug('Enqueued ' + str(count) + ' items for upload, upload_queue size is now ' + str(upload_queue.qsize()))
                        else:
                            logging.debug('Nothing to upload, skipping check until more data is inserted to the db')
                            db_empty = True
                            
                     #4. Update the STAcounter (still alive watchdog) on the UPS Pico over i2c, only if gpio 16 (pin 36) is jumpered to it's adjacent ground pin, the pull up was configured earlier.
                    if(STACounterEnabled):
                        pi.i2c_write_byte_data(i2c_handle_6b, 0x08, 180) #UPS Pico will initiate a reboot if this line of code is not successfully executed at least once in 3 minutes (it counts down).
                    if(i2c_handle_6b >= 0):
                        toggle_val = 1 - toggle_val
                        pi.write(13,toggle_val) #pin 33, connected to trinket watchdog  
                        pi.i2c_write_byte_data(i2c_handle_6b, 0x0C, toggle_val) #toggle the blue LED to visually show we hit the watchdog code
        
                elif (command == 'sent'): 
                    c = conn.cursor()
                    c.execute('''DELETE FROM datapoints WHERE id=?''', (message[1],))
                    logging.debug('Successfully sent a msg with id ' + str(message[1]))
                    continue
                elif (command == 'set ready_to_upload'):
                    logging.debug('Upload queue is ready for more data')
                    ready_to_upload = True
                elif (command == 'invalid date'):
                    if(not invalid_date):
                        logging.info('Invalid date flag set.')
                        invalid_date = True
                elif (command == 'quit'):
                    logging.error('Stopping main thread due to an error.')
                    killer.kill_self()
                elif (command == 'upload thread stopped'):
                    upload_thread_running = False
                elif (command == 'DAQ thread stopped'):
                    daq_thread_running = False
                    killer.kill_self()
    except:
        logging.error('Main thread exception: ' + traceback.format_exc())
        killer.kill_self()
        sys.exit(1)
    finally:
        systemd_status(*notify, status=b"Shutting down")
        if(conn is not None):
            conn.commit()
            conn.close()
            logging.info('Database committed and closed.')
        try:
            if(b is not None):
                logging.info('Waiting up to 10 seconds for DAQ thread to fully stop.')
                #new_data_event.set() #wake up thread so it checks killer.kill_now flag
                b.join(10)
            if(i2c_handle_6b >= 0):
                logging.info('Turning off blue LED.')
                try:
                    pi.i2c_write_byte_data(i2c_handle_6b, 0x0C, 0) #turn off the blue LED
                except:
                    pass
            try:
                logging.info('Closing i2c handles.')
                pi.i2c_close(i2c_handle_6b)
            except:
                pass
            try:
                pi.i2c_close(i2c_handle_69)
            except:
                pass
            try:
                pi.i2c_close(i2c_handle_ADS7828)
            except:
                pass
        except:
            pass
        finally:
            if(pi is not None):
                logging.info('Closing pigpio socket.')
                pi.stop()        
        logging.info('Exiting.')
        systemd_stop(*notify)
        return


def notify_socket(clean_environment=True):
    """Return a tuple of address, socket for future use.

    clean_environment removes the variables from env to prevent children
    from inheriting it and doing something wrong.
    """
    _empty = None, None
    address = os.environ.get("NOTIFY_SOCKET", None)
    if clean_environment:
        address = os.environ.pop("NOTIFY_SOCKET", None)

    if not address:
        return _empty

    if len(address) == 1:
        return _empty

    if address[0] not in ("@", "/"):
        return _empty

    if address[0] == "@":
        address = "\0" + address[1:]

    # SOCK_CLOEXEC was added in Python 3.2 and requires Linux >= 2.6.27.
    # It means "close this socket after fork/exec()
    try:
        sock = socket.socket(socket.AF_UNIX,
                             socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)
    except AttributeError:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    return address, sock


def sd_message(address, sock, message):
    """Send a message to the systemd bus/socket.

    message is expected to be bytes.
    """
    if not (address and sock and message):
        return False
    assert isinstance(message, bytes)

    try:
        retval = sock.sendto(message, address)
    except socket.error:
        return False
    return (retval > 0)


def watchdog_ping(address, sock):
    """Helper function to send a watchdog ping."""
    message = b"WATCHDOG=1"
    return sd_message(address, sock, message)


def systemd_ready(address, sock):
    """Helper function to send a ready signal."""
    message = b"READY=1"
    logging.debug("Signaling system ready")
    return sd_message(address, sock, message)


def systemd_stop(address, sock):
    """Helper function to signal service stopping."""
    message = b"STOPPING=1"
    return sd_message(address, sock, message)


def systemd_status(address, sock, status):
    """Helper function to update the service status."""
    message = ("STATUS=%s" % status).encode('utf8')
    return sd_message(address, sock, message)

def connectPiGPIO(): #see http://abyz.co.uk/rpi/pigpio/pigpiod.html
    logging.info('restarting pigpio to reset all handles')
    os.system('systemctl restart pigpiod')
    pi = None #pigpiod connection
    connected = False
    begin = time.time()
    time.sleep(1) #give it some time to initialize
    while not connected:
        try:
            pi = pigpio.pi() #opens a local connection using defaults to the pigpio daemon we just launched
            connected = pi.connected
            if(connected):
                logging.info('Successfully connected to pigpiod')
            else:
                raise EnvironmentError('Could not connect to pigpiod.');
            break
        except:
            if(time.time() - begin > 10):
                raise
            else:
                time.sleep(1)
                pass
    return pi

def open_UPS_i2C_handles(pi): #opening i2c handles to UPS Pico LED and watchdog registers, see http://www.modmypi.com/raspberry-pi/breakout-boards/pi-modules/ups-pico for manual
        i2c_handle_6b = pi.i2c_open(1, 0x6B) #i2c bus 1, register 0x6b, 
        i2c_handle_69 = pi.i2c_open(1, 0x69) #i2c bus 1, register 0x69, also analog input on Pico UPS
        i2c_handle_AD7828 = pi.i2c_open(1, 0x48) #i2c bus 1, 0x48 is the default address of the AD7828
        fw_version = pi.i2c_read_byte_data(i2c_handle_6b, 0x00)
        if(i2c_handle_6b >= 0 and i2c_handle_69 >=0 and int(fw_version) > 0):
            logging.info('Successfully communicated with UPS Pico, firmware version is ' + '{:02x}'.format(fw_version))
        if(i2c_handle_6b < 0 or i2c_handle_69 < 0 or i2c_handle_AD7828 < 0):
            raise Exception('The i2c handles are invalid (<0)')
        return (i2c_handle_6b, i2c_handle_69, i2c_handle_AD7828)
    
if __name__ == '__main__':
    
    killer = Killer()
    init_logger()
    
    notify = notify_socket()
    
    if not notify[0]:
        logging.error("No notification socket, not launched via systemd?")

    # Start processing
    systemd_status(*notify, status=b"Initializing")
    logging.info("Signalling ready")
    systemd_ready(*notify)
    
    mainloop(notify, killer)
