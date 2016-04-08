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


import RPi.GPIO as GPIO
import os, sys, signal, inspect, platform, traceback
import serial,  serial.tools.list_ports #see https://learn.adafruit.com/arduino-lesson-17-email-sending-movement-detector/installing-python-and-pyserial for install instructions on windows
import sqlite3
import time
import socket
import threading, queue
import requests
import logging, logging.handlers

def find_Arduino_Serial_Port():
    fail_count = 0
    vid = "vid:pid=0e8d:0023" #VID for MediaTek Inc., manufacturer of LinkIt One
    vendor = 'mtk' #mediatek
    linux_port_prefix = '/dev/ttyacm0'
    blacklist = ('/dev/ttyacm1', 'com23')
    
    while True:
        logging.info('Searching for arduino serial port..')
        portList = sorted(serial.tools.list_ports.comports())
        for port in portList:
            if vendor in str(port[1]).lower() or vid in str(port[2]).lower():
                portname = str(port[0]).replace('b','').replace("'",'')
                port_valid = True
                for invalid_port in blacklist:
                    if(invalid_port in portname):
                        port_valid = False
                if(port_valid):
                    logging.info("Arduino found at " + portname)
                    return portname
        fail_count += 1
        time.sleep(5)
        if(fail_count >= 3): #15 seconds have passed with no device found
            logging.error('Failed to find the arduino serial port')
            reset_arduino(10)
            fail_count = 0
    
def reset_arduino(wait_time = 10):
    logging.info('Doing reset pulse on rpi GPIO header pin 11 (BCM 17)...')
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(11, GPIO.OUT)
    GPIO.output(11,False)
    time.sleep(0.2)
    GPIO.cleanup()
    if(wait_time > 0):
        logging.info('Sleeping ' + str(wait_time) + ' seconds for arduino bootup...')
        time.sleep(10) #give the device some time to bootup


def acquire_data(main_queue, killer):
    time_format_str = '%Y-%m-%dT%H:%M:%S'
    ser = None

    while not killer.kill_now:
        try:
            serPort = find_Arduino_Serial_Port()
            
            ser = None
            read_fail_count = 0

            
            logging.debug('acquire_data process launched and serial port opened...')
            while not killer.kill_now:
                try:
                    if(ser is None or not ser.isOpen()):
                        ser = serial.Serial(serPort, timeout=1) 

                    data = ser.readline()
                    
                    if(killer.kill_now):
                        break
                    
                    data_split = None
                    if(data is not None and len(data) > 0):
                        data = data.decode('utf-8').rstrip('\r\n')
                        data_split = data.split('Z,')
                    
                    if(data_split is None or len(data_split) < 2):
                        read_fail_count = read_fail_count + 1
                        if(read_fail_count < 60):
                            continue
                        else:
                            logging.error('No data has been received for 60 seconds, resetting arduino and restarting this application')
                            reset_arduino(0)
                            main_queue.put(('quit',), block=False) 
                            break
                    #print(data)
                    read_fail_count = 0 #we didn't timeout, so reset the fail counter   
                    timestr = data_split[0]
                    
                    timetup = time.strptime(timestr, time_format_str)
                    year_from_GPS = int(time.strftime("%Y", timetup))
                    
                    if year_from_GPS <= 2004: #we do not have a valid time stamp, probably due to no GPS fix.
                        pi_has_correct_time = int(time.strftime("%Y")) > 2004
                        if(pi_has_correct_time):
                            timestr = time.strftime(time_format_str)
                            timetup = time.strptime(timestr, time_format_str)
                        else:
                            logging.info('Discarding data becuase timestamp is <= 2004 ' + data)
                            continue

                    data_str = timestr + 'Z,' + data_split[1]
                    if(len(data_str.split(',')) < 9):
                        logging.debug('Invalid serial data recieved, length < 9 after split on , ACTUAL DATA: ' + data)
                        continue
                    filename = time.strftime("%Y-%m-%d_%H.csv", timetup) #change log file every hour
                    main_queue.put(('new data', filename, data_str))                
                except ValueError:
                    pass
        except Exception as ex:
            logging.error('acquire_data: ' + traceback.format_exc())
            pass
        finally:
            if (ser is not None):
                 if ser.isOpen():
                    ser.close()
                    logging.info('Serial port closed.')
            main_queue.put(('DAQ thread stopped',))
            logging.debug('DAQ thread is exiting.')

       


def keyword_args_to_dict(**kwargs):
    return {k: v for (k,v) in kwargs.items() if v != None}
    
def upload_data_to_thingspeak(upload_queue, main_queue, db_file_path, killer):
    
    #**********thingspeak configuration*************#
    NUMOFCHANNELS = 5
    url = 'https://api.thingspeak.com/update'
    field_keys = ['field' + str(n) for n in range(1,NUMOFCHANNELS+1)]
    headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
    write_key = 'ODZXE1UNTM1825OX' #<--THAT'S TREVER'S TEST CHANNEL, original #WeirTest key: 'ZHHHO6RTJOAHCAYW'
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
                queue_timeouts = queue_timeouts + 1
                if(queue_timeouts < 120):
                    continue
                else:
                    raise
            finally:
                if(stopping_upload_thread):
                    logging.debug('Upload process caught stop signal')
                    break

            queue_timeouts = 0 #we didn't timeout!, so reset the counter here.
            
            row_id = msg[0]
            logging.debug('Upload msg received: ' + msg[1])
            field_values = msg[1].split(',')
            
            seconds_since_last_post = time.time() - time_of_last_post_attempt
                
            if(seconds_since_last_post < post_interval):
                seconds_to_sleep = post_interval - seconds_since_last_post
                #logging.debug('Upload thread is going to sleep for ' + '{0:.1f}'.format(seconds_to_sleep) + ' seconds')
                time.sleep(seconds_to_sleep)

            #logging.debug('Length of field values list: ' + str(len(field_values)))        
            logging.debug(str(upload_queue.qsize()) + ' items left in upload queue')
            upload_success =  False
            try:
                data = dict(zip(field_keys, [field_values[4], field_values[5], field_values[6], field_values[7],field_values[8]]))
                optional_args = keyword_args_to_dict(created_at = field_values[0], lat=field_values[1], long=field_values[2], elevation=field_values[3])
                params = dict(data.items() |  api_keys.items() | optional_args.items())
                thingspeak_reply = session.post(url, params, timeout = 6.1)
                upload_success = thingspeak_reply is not None and thingspeak_reply.text.isdigit() and int(thingspeak_reply.text) > 0
                logging.info("Attempted to post a datapoint with timestamp " +  field_values[0] + ", reply from thingspeak: " + thingspeak_reply.text)
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
#    script_path = os.path.dirname(os.path.abspath(script_filename))
    script_path = '/media/usb0'
    directory = os.path.join(script_path, "CSV_Files")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def get_Event_Log_Folder_Path():
    script_filename = inspect.getframeinfo(inspect.currentframe()).filename
#    script_path = os.path.dirname(os.path.abspath(script_filename))
    script_path = '/media/usb0'
    directory = os.path.join(script_path, "Eventlogs")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def get_Database_File_Path():
    script_filename = inspect.getframeinfo(inspect.currentframe()).filename
    #script_path = os.path.dirname(os.path.abspath(script_filename))
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

        #create rotating file handler and set level to error
        TEMP_LOG_PATH = os.path.join('/var/log', 'datacollection.log')
        handler = logging.handlers.RotatingFileHandler(TEMP_LOG_PATH, maxBytes = 1048576, backupCount = 4)# keep last 5 MB of logs in 1 MB files
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.debug('/var/log/datacollection.log logging initialized')

        #create console handler and set level to info
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.debug('stdout logging initialized')

        
        #create rotating file handler and set level to error
        EVENT_LOG_PATH = os.path.join(get_Event_Log_Folder_Path(), 'log.out')
        handler = logging.handlers.RotatingFileHandler(EVENT_LOG_PATH, maxBytes = 1048576, backupCount = 4) #keep last 5 MB of logs in 1 MB files
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logging.debug('USB logging initialized')

        



#**********thingspeak configuration*************#

class Killer:
  kill_now = False
  def __init__(self):
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, self.exit)
        
  def kill_self(self):
      if(not self.kill_now):
          logging.debug('Shutdown request variable set from within this program, attempting to shutdown nicely...')
          systemd_status(*notify, status=b"Shutting down")
          self.kill_now = True

  def exit(self,signum, frame):
    logging.debug('An OS kill signal was caught, attempting to shutdown nicely...')
    systemd_status(*notify, status=b"Shutting down")
    self.kill_now = True


def mainloop(notify):
    """A simple mainloop, spinning 100 times.

    Uses the probability flag to test how likely it is to cause a
    watchdog error.
    """
    systemd_status(*notify,
                   status="Mainloop started")

    conn = None

    try:
        global stopping_upload_thread #written in main, read in upload function
                                      
        previous_filepath = current_log_filepath = None 
        
        upload_queue = queue.Queue(100)
        main_queue = queue.Queue(1000)

        db_file_path = init_db()
        
        conn = sqlite3.connect(db_file_path)
                                
        base_log_directory = get_CSV_Folder_Path()

        #reset_arduino(10)        
        logging.info('Launching data acquisition and upload threads...')
        
        a = threading.Thread(target=upload_data_to_thingspeak, args=(upload_queue, main_queue, db_file_path, killer))
        a.daemon = True
        a.start()
        upload_thread_running = True
        
        b = threading.Thread(target=acquire_data, args=(main_queue, killer))
        b.daemon = True
        b.start()

    
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

                message = main_queue.get(block=True, timeout=120) #application should quit if nothing happens for 120 seconds
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
                        logging.debug('Inserting new data, main_queue size ' + str(main_queue.qsize()))
                        last_insert = time.time()
                        c = conn.cursor()
                        c.execute('''INSERT INTO datapoints (datapoint) VALUES (?)''', (message[2],))
                        db_empty = False
                        conn.commit()
                        logging.debug('insert done')
                        
                    #3. Check if the upload queue is ready to send more data:
                        #the following 'if' checks that the upload thread has sent it's ready signal (set ready_to_upload),
                        #and checks a flag indicating that the database possibly has data waiting to be sent, and there are no pending deletes (main_queue.empty())

                    if(ready_to_upload and not db_empty and main_queue.empty()): 
                        logging.debug('Fetching data to upload...')
                        c.execute('''SELECT * FROM datapoints ORDER BY id DESC LIMIT 3''')

                        #only send most recent 3 datapoints at a time (id PK auto increments as data is added).
                        #mainly becuase thingspeak only lets us update every 15 seconds, and new data will be inserted, queued up and posted once a minute.
                        #This way, if we have a large backlog we will still post the most recent data  as it rolls in but slowly work through the backlog as time allows

                        results = c.fetchall()
                        if(results):
                            count = 0
                            for data in results:
                                count += 1
                                upload_queue.put(data)
                            ready_to_upload = False #reset ready signal, will get set when the upload queue has finished with this chunk of results
                            logging.debug('Queued ' + str(count) + ' items for upload, upload_queue size is now ' + str(upload_queue.qsize()))
                        else:
                            logging.debug('Nothing to upload, skipping check until more data is inserted to the db')
                            db_empty = True
                elif (command == 'sent'): 
                    logging.debug('Deleting a sent row')
                    c = conn.cursor()
                    c.execute('''DELETE FROM datapoints WHERE id=?''', (message[1],))
                    logging.debug('Deleted id ' + str(message[1]))
                    continue
                elif (command == 'set ready_to_upload'):
                    logging.debug('Upload queue is ready for more data')
                    ready_to_upload = True
                elif (command == 'quit'):
                    logging.error('Stopping main thread due to an error.')
                    killer.kill_self()
                elif (command == 'upload thread stopped'):
                    upload_thread_running = False
                elif (command == 'DAQ thread stopped'):
                    killer.kill_self()
    except:
        logging.error('Main thread exception: ' + traceback.format_exc())
        killer.kill_self()
        sys.exit(1)
    finally:
        if(conn is not None):
            conn.commit()
            conn.close()
            logging.info('Database committed and closed.')
        logging.info('Program exiting.')
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


def print_err(msg):
    """Print an error message to STDERR and quit."""
    print(msg, file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    killer = Killer()
    init_logger()
        
    # Get our settings from the environment
    notify = notify_socket()
    # Validate some in-data
    if not notify[0]:
        print_err("No notification socket, not launched via systemd?")

    # Start processing
    systemd_status(*notify, status=b"Initializing")

    logging.info("Signalling ready")
    
    systemd_ready(*notify)

    mainloop(notify)
