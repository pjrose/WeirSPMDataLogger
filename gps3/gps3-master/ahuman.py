#!/usr/bin/env python3
# coding=utf-8

"""
human.py is to showcase agps3.py, a Python 2.7-3.5 GPSD interface
Defaults host='127.0.0.1', port=2947, gpsd_protocol='json'

Toggle Lat/Lon form with '0', '1', '2', '3' for RAW, DDD, DMM, DMS

Toggle units with  '0', 'm', 'i', 'n', for 'raw', Metric, Imperial, Nautical

Quit with 'q' or '^c'

python[X] human.py --help for list of commandline options.
"""

import argparse
import curses
import sys
from datetime import datetime
from math import modf
from time import sleep

from gps3 import agps3

__author__ = 'Moe'
__copyright__ = "Copyright 2015-2016  Moe"
__license__ = "MIT"
__version__ = "0.20"

CONVERSION = {'raw': (1, 1, 'm/s', 'meters'),
              'metric': (3.6, 1, 'kph', 'meters'),
              'nautical': (1.9438445, 1, 'kts', 'meters'),
              'imperial': (2.2369363, 3.2808399, 'mph', 'feet')}


def add_args():
    """Adds commandline arguments and formatted Help"""
    parser = argparse.ArgumentParser()

    parser.add_argument('-host', action='store', dest='host', default='127.0.0.1', help='DEFAULT "127.0.0.1"')
    parser.add_argument('-port', action='store', dest='port', default='2947', help='DEFAULT 2947', type=int)
    parser.add_argument('-json', dest='gpsd_protocol', const='json', action='store_const', default='json', help='DEFAULT JSON objects */')
    parser.add_argument('-device', dest='devicepath', action='store', help='alternate devicepath e.g.,"-device /dev/ttyUSB4"')
    # Infrequently used options
    parser.add_argument('-nmea', dest='gpsd_protocol', const='nmea', action='store_const', help='*/ output in NMEA */')
    parser.add_argument('-rare', dest='gpsd_protocol', const='rare', action='store_const', help='*/ output of packets in hex */')
    parser.add_argument('-raw', dest='gpsd_protocol', const='raw', action='store_const', help='*/ output of raw packets */')
    parser.add_argument('-scaled', dest='gpsd_protocol', const='scaled', action='store_const', help='*/ scale output to floats */')
    parser.add_argument('-timing', dest='gpsd_protocol', const='timing', action='store_const', help='*/ timing information */')
    parser.add_argument('-split24', dest='gpsd_protocol', const='split24', action='store_const', help='*/ split AIS Type 24s */')
    parser.add_argument('-pps', dest='gpsd_protocol', const='pps', action='store_const', help='*/ enable PPS JSON */')

    args = parser.parse_args()
    return args


def satellites_used(feed):
    """Counts number of satellites use in calculation from total visible satellites
    Arguments:
        feed feed=dot.satellites
    Returns:
        total_satellites(int):
        used_satellites (int):
    """
    total_satellites = 0
    used_satellites = 0

    if not isinstance(feed, list):
        return 0, 0

    for satellites in feed:
        total_satellites += 1
        if satellites['used'] is True:
            used_satellites += 1
    return total_satellites, used_satellites


def make_time(gps__datetime_str):
    """Makes datetime object from string object"""
    if not 'n/a' == gps__datetime_str:
        datetime_string = gps__datetime_str
        datetime_object = datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S")
        return datetime_object


def elapsed_time_from(start_time):
    """calculate time delta from latched time and current time"""
    time_then = make_time(start_time)
    time_now = datetime.utcnow().replace(microsecond=0)
    if time_then is None:
        return
    delta_t = time_now - time_then
    return delta_t


def unit_conversion(thing, units, length=False):
    """converts base data between metric, imperial, or natical units"""
    if 'n/a' == thing:
        return 'n/a'
    try:
        thing = round(thing * CONVERSION[units][0 + length], 2)
    except:
        thing = 'fubar'
    return thing, CONVERSION[units][2 + length]


def sexagesimal(sexathang, tag, form='DDD'):
    """
    Arguments:
        sexathang: (float), -15.560615 (negative = South), -146.241122 (negative = West)  # Apataki Carenage
        tag: (str) 'lat' | 'lon'
        form: (str), 'DDD'|'DMM'|'DMS', decimal Degrees, decimal Minutes, decimal Seconds
    Returns:
        latitude: e.g., '15°33'38.214" S'
        longitude: e.g., '146°14'28.039" W'
    """
    cardinal = 'O'
    if not isinstance(sexathang, float):
        sexathang = 'n/a'
        return sexathang

    if tag == 'lon':
        if sexathang > 0.0:
            cardinal = 'E'
        if sexathang < 0.0:
            cardinal = 'W'

    if tag == 'lat':
        if sexathang > 0.0:
            cardinal = 'N'
        if sexathang < 0.0:
            cardinal = 'S'

    if form == 'RAW':
        sexathang = '{0:4.6f}°'.format(sexathang)
        return sexathang

    if form == 'DDD':
        sexathang = '{0:3.6f}°'.format(abs(sexathang))

    if form == 'DMM':
        _latlon = abs(sexathang)
        minute_latlon, degree_latlon = modf(_latlon)
        minute_latlon *= 60
        sexathang = '{0}° {1:2.5f}\''.format(int(degree_latlon), minute_latlon)

    if form == 'DMS':
        _latlon = abs(sexathang)
        minute_latlon, degree_latlon = modf(_latlon)
        second_latlon, minute_latlon = modf(minute_latlon * 60)
        second_latlon *= 60.0
        sexathang = '{0}° {1}\' {2:2.3f}\"'.format(int(degree_latlon), int(minute_latlon), second_latlon)

    return sexathang + cardinal


def show_human():
    """Curses terminal with standard outputs """
    args = add_args()
    gps_connection = agps3.GPSDSocket(args.host, args.port, args.gpsd_protocol, args.devicepath)
    dot = agps3.Dot()
    form = 'RAW'
    units = 'raw'
    # units = 'metric'
    screen = curses.initscr()
    screen.clear()
    screen.scrollok(True)
    curses.noecho()
    curses.curs_set(0)
    curses.cbreak()

    data_window = curses.newwin(19, 39, 1, 1)
    sat_window = curses.newwin(19, 39, 1, 40)
    device_window = curses.newwin(6, 39, 14, 40)
    packet_window = curses.newwin(20, 78, 20, 1)

    try:
        for new_data in gps_connection:
            if new_data:
                dot.unpack(new_data)

                screen.nodelay(1)
                event = screen.getch()

                if event == ord('q'):
                    shut_down(gps_connection)
                elif event == ord('0'):  # raw
                    form = 'RAW'
                    units = 'raw'
                    data_window.clear()
                elif event == ord("1"):  # DDD
                    form = 'DDD'
                    data_window.clear()
                elif event == ord('2'):  # DMM
                    form = 'DMM'
                    data_window.clear()
                elif event == ord("3"):  # DMS
                    form = 'DMS'
                    data_window.clear()
                elif event == ord("m"):  # Metric
                    units = 'metric'
                    data_window.clear()
                elif event == ord("i"):  # Imperial
                    units = 'imperial'
                    data_window.clear()
                elif event == ord("n"):  # Nautical
                    units = 'nautical'
                    data_window.clear()

                data_window.box()
                data_window.addstr(0, 2, 'GPS3 Python {}.{}.{} GPSD Interface'.format(*sys.version_info), curses.A_BOLD)
                data_window.addstr(1, 2, 'Time:  {} '.format(dot.time))
                data_window.addstr(2, 2, 'Latitude:  {} '.format(sexagesimal(dot.lat, 'lat', form)))
                data_window.addstr(3, 2, 'Longitude: {} '.format(sexagesimal(dot.lon, 'lon', form)))
                data_window.addstr(4, 2, 'Altitude:  {} {}'.format(*unit_conversion(dot.alt, units, length=True)))
                data_window.addstr(5, 2, 'Speed:     {} {}'.format(*unit_conversion(dot.speed, units)))
                data_window.addstr(6, 2, 'Heading:   {}° True'.format(dot.track))
                data_window.addstr(7, 2, 'Climb:     {} {}'.format(*unit_conversion(dot.climb, units, length=True)))
                data_window.addstr(8, 2, 'Status:     {:<}D  '.format(dot.mode))
                data_window.addstr(9, 2, 'Latitude Err:  +/-{} {}'.format(*unit_conversion(dot.epx, units, length=True)))
                data_window.addstr(10, 2, 'Longitude Err: +/-{} {}'.format(*unit_conversion(dot.epy, units, length=True)))
                data_window.addstr(11, 2, 'Altitude Err:  +/-{} {}'.format(*unit_conversion(dot.epv, units, length=True)))
                data_window.addstr(12, 2, 'Course Err:    +/-{}   '.format(dot.epc), curses.A_DIM)
                data_window.addstr(13, 2, 'Speed Err:     +/-{} {}'.format(*unit_conversion(dot.eps, units)), curses.A_DIM)
                data_window.addstr(14, 2, 'Time Offset:   +/-{}  '.format(dot.ept), curses.A_DIM)
                data_window.addstr(15, 2, 'gdop:{}  pdop:{}  tdop:{}'.format(dot.gdop, dot.pdop, dot.tdop))
                data_window.addstr(16, 2, 'ydop:{}  xdop:{} '.format(dot.ydop, dot.xdop))
                data_window.addstr(17, 2, 'vdop:{}  hdop:{} '.format(dot.vdop, dot.hdop))

                sat_window.clear()
                sat_window.box()
                sat_window.addstr(0, 2, 'Using {0[1]}/{0[0]} satellites (truncated)'.format(satellites_used(dot.satellites)))
                sat_window.addstr(1, 2, 'PRN     Elev   Azimuth   SNR   Used')
                line = 2
                if isinstance(dot.satellites, list):  # Nested lists of dictionaries are strings before data is present
                    for sats in dot.satellites[0:10]:
                        sat_window.addstr(line, 2, '{PRN:>2}   {el:>6}   {az:>5}   {ss:>5}   {used:}'.format(**sats))
                        line += 1

                # device_window.clear()
                device_window.box()
                if not isinstance(dot.devices, list):
                    gps_connection.send('?DEVICES;')  # Local machines need a 'device' kick start to have valid data I don't know why.

                if isinstance(dot.devices, list):
                    for gizmo in dot.devices:
                        start_time, _uicroseconds = gizmo['activated'].split('.')  # Remove '.000Z'
                        elapsed = elapsed_time_from(start_time)

                        device_window.addstr(1, 2, 'Activated: {}'.format(gizmo['activated']))
                        device_window.addstr(2, 2, 'Host:{0.host}:{0.port} {1}'.format(args, gizmo['path']))
                        device_window.addstr(3, 2, 'Driver:{driver} BPS:{bps}'.format(**gizmo))
                        device_window.addstr(4, 2, 'Cycle:{0} Hz {1!s:>14} Elapsed'.format(gizmo['cycle'], elapsed))

                packet_window.clear()
                packet_window.border(0)
                packet_window.scrollok(True)
                packet_window.addstr(0, 0, '{}'.format(new_data))

                sleep(.4)

                data_window.refresh()
                sat_window.refresh()
                device_window.refresh()
                packet_window.refresh()

    except KeyboardInterrupt:
        shut_down(gps_connection)

def shut_down(gps_connection):
    """Closes connection and restores terminal"""
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    gps_connection.close()
    print("Keyboard interrupt received\nTerminated by user\nGood Bye.\n")
    sys.exit(1)


if __name__ == '__main__':
    try:

        if 'json' in add_args().gpsd_protocol:
            show_human()
        if 'nmea' in add_args().gpsd_protocol:
            show_nmea()

    except KeyboardInterrupt:
        shut_down(show_human().gps_connection)
#
# Someday a cleaner Python interface will live here
#
# End
