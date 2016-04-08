#!/usr/bin/env python3
# coding=utf-8

"""
human.py is to showcase gps3.py, a Python 2.7-3.5 GPSD interface
Defaults host='127.0.0.1', port=2947, gpsd_protocol='json'

Toggle Lat/Lon form with '0', '1', '2', '3' for RAW, DDD, DMM, DMS

Toggle units with  '0', 'm', 'i', 'n', for 'raw', Metric, Imperial, Nautical

Quit with 'q' or '^c'

python[X] human.py --help for list of commandline options.
"""

from datetime import datetime
from math import modf
from time import sleep

from gps3 import gps3

__author__ = 'Moe'
__copyright__ = "Copyright 2015-2016  Moe"
__license__ = "MIT"
__version__ = "0.20"

CONVERSION = {'raw': (1, 1, 'm/s', 'meters'),
              'metric': (3.6, 1, 'kph', 'meters'),
              'nautical': (1.9438445, 1, 'kts', 'meters'),
              'imperial': (2.2369363, 3.2808399, 'mph', 'feet')}


def satellites_used(feed):
    """Counts number of satellites use in calculation from total visible satellites
    Arguments:
        feed feed=gps_fix.TPV['satellites']
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

