#!/usr/bin/python
'''*****************************************************************************************************************
    Pi Temperature Station
    By John M. Wargo
    www.johnwargo.com

    Edited by Tom Nummy to use temper-usb

    This is a Raspberry Pi project that measures weather values (temperature, humidity and pressure) using
    the Astro Pi Sense HAT then uploads the data to a Weather Underground weather station.
********************************************************************************************************************'''

from __future__ import print_function

import datetime
import os
import sys
import time
import json
from urllib import urlencode

import urllib2
from sense_hat import SenseHat

from config import Config

sys.path.insert(0, 'temperusb')
import temper

# ============================================================================
# Constants
# ============================================================================
# specifies how often to measure values from the Sense HAT (in minutes)
MEASUREMENT_INTERVAL = 2  # minutes
# Set to False when testing the code and/or hardware
# Set to True to enable upload of weather data to Weather Underground
WEATHER_UPLOAD = True
# the weather underground URL used to upload weather data
WU_URL = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
# some string constants
SINGLE_HASH = "#"
HASHES = "########################################"
SLASH_N = "\n"


def c_to_f(input_temp):
    # convert input_temp from Celsius to Fahrenheit
    return (input_temp * 1.8) + 32


def get_cpu_temp():
    # 'borrowed' from https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # executes a command at the OS to pull in the CPU temperature
    res = os.popen('vcgencmd measure_temp').readline()
    return float(res.replace("temp=", "").replace("'C\n", ""))


# use moving average to smooth readings
def get_smooth(x):
    # do we have the t object?
    if not hasattr(get_smooth, "t"):
        # then create it
        get_smooth.t = [x, x, x]
    # manage the rolling previous values
    get_smooth.t[2] = get_smooth.t[1]
    get_smooth.t[1] = get_smooth.t[0]
    get_smooth.t[0] = x
    # average the three last temperatures
    xs = (get_smooth.t[0] + get_smooth.t[1] + get_smooth.t[2]) / 3
    return xs


def get_temp():
    # ====================================================================
    # Unfortunately, getting an accurate temperature reading from the
    # Sense HAT is improbable, see here:
    # https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # so we'll have to do some approximation of the actual temp
    # taking CPU temp into account. The Pi foundation recommended
    # using the following:
    # http://yaab-arduino.blogspot.co.uk/2016/08/accurate-temperature-reading-sensehat.html
    # ====================================================================
    # First, get temp readings from both sensors
    t1 = sense.get_temperature_from_humidity()
    t2 = sense.get_temperature_from_pressure()
    # t becomes the average of the temperatures from both sensors
    t = (t1 + t2) / 2
    # Now, grab the CPU temperature
    t_cpu = get_cpu_temp()
    # Calculate the 'real' temperature compensating for CPU heating
    #t_corr = t - ((t_cpu - t) / 1.5)
    t_corr = t - ((t_cpu - t) / 0.85)
    # Finally, average out that value across the last three readings
    t_corr = get_smooth(t_corr)
    # convoluted, right?
    # Return the calculated temperature
    return t_corr

def get_temper_temp():
    return temper_device.get_temperature()

def get_humidity_temp():
    return sense.get_temperature_from_humidity()

def get_pressure_temp():
    return sense.get_temperature_from_pressure()

def main():
    global last_temp

    # initialize the lastMinute variable to the current time to start
    last_minute = datetime.datetime.now().minute
    # on startup, just use the previous minute as lastMinute
    last_minute -= 1
    if last_minute == 0:
        last_minute = 59

    # infinite loop to continuously check weather values
    while 1:
        # The temp measurement smoothing algorithm's accuracy is based
        # on frequent measurements, so we'll take measurements every 5 seconds
        # but only upload on measurement_interval
        current_second = datetime.datetime.now().second
        # are we at the top of the minute or at a 5 second interval?
        if (current_second == 0) or ((current_second % 5) == 0):
            # ========================================================
            # read values from the Sense HAT
            # ========================================================
            # Calculate the temperature. The get_temp function 'adjusts' the recorded temperature adjusted for the
            # current processor temp in order to accommodate any temperature leakage from the processor to
            # the Sense HAT's sensor. This happens when the Sense HAT is mounted on the Pi in a case.
            # If you've mounted the Sense HAT outside of the Raspberry Pi case, then you don't need that
            # calculation. So, when the Sense HAT is external, replace the following line (comment it out  with a #)
            calc_temp = get_temp()
            t_temp_c    = get_temper_temp()

            temp_c = round(calc_temp, 2)
            temp_f = round(c_to_f(calc_temp), 2)
            temp_cpu = c_to_f(get_cpu_temp())
            t_temp_f = c_to_f(t_temp_c)

            humidity = round(sense.get_humidity(), 2)
            # convert pressure from millibars to inHg before posting
            pressure = round(sense.get_pressure() * 0.0295300, 2)
            print("Temp: %sF (%sC), Pressure: %s inHg, Humidity: %s%%" % (t_temp_f, t_temp, pressure, humidity))
            # get the current minute
            current_minute = datetime.datetime.now().minute
            # is it the same minute as the last time we checked?
            if current_minute != last_minute:
                # reset last_minute to the current_minute
                last_minute = current_minute
		# adding in a display message to the sense hat
		sense.show_message('... '+str(last_temp)+" F -  "+str(pressure)+" inHg - "+str(humidity)+" %H", text_colour=(0,255,0))
                # is minute zero, or divisible by 10?
                # we're only going to take measurements every MEASUREMENT_INTERVAL minutes
                if (current_minute == 0) or ((current_minute % MEASUREMENT_INTERVAL) == 0):
                    # get the reading timestamp
                    now = datetime.datetime.now()
                    print("\n%d minute mark (%d @ %s)" % (MEASUREMENT_INTERVAL, current_minute, str(now)))

                    # set last_temp to the current temperature before we measure again
                    last_temp = t_temp_f
                    # ========================================================
                    # Save to local log file
                    # ========================================================
                    entry = {'datetime'   : datetime.datetime.now(),
                            'temper_temp' : t_temp_f,
                            'sense_temp'  : temp_f,
                            'sense_humd'  : humidity,
                            'sense_pres'  : pressure,
                            'cpu_temp'    : temp_cpu
                            }
                    with open(log_name, 'r') as feedjson:
                        feed = json.load(feedjson)
                    feed.append(entry)
                    with open(log_name, 'w') as jsonf:
                        json.dump(feed, jsonf)

                    # ========================================================
                    # Upload the weather data to Weather Underground
                    # ========================================================
                    # is weather upload enabled (True)?
                    if WEATHER_UPLOAD:
                        # From http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
                        print("Uploading data to Weather Underground")
                        # build a weather data object
                        weather_data = {
                            "action": "updateraw",
                            "ID": wu_station_id,
                            "PASSWORD": wu_station_key,
                            "dateutc": "now",
                            "tempf": str(t_temp_f),
                            "humidity": str(humidity),
                            "baromin": str(pressure),
                        }
                        try:
                            upload_url = WU_URL + "?" + urlencode(weather_data)
                            response = urllib2.urlopen(upload_url)
                            html = response.read()
                            print("Server response:", html)
                            # do something
                            response.close()  # best practice to close the file
                        except:
                            print("Exception:", sys.exc_info()[0], SLASH_N)
                    else:
                        print("Skipping Weather Underground upload")

        # wait a second then check again
        # You can always increase the sleep value below to check less often
        time.sleep(1)  # this should never happen since the above is an infinite loop

    print("Leaving main()")


# ============================================================================
# here's where we start doing stuff
# ============================================================================
print(SLASH_N + HASHES)
print(SINGLE_HASH, "Pi Weather Station                  ", SINGLE_HASH)
print(SINGLE_HASH, "By John M. Wargo (www.johnwargo.com)", SINGLE_HASH)
print(SINGLE_HASH, "Edited By Tom Nummy", SINGLE_HASH)
print(HASHES)

# make sure we don't have a MEASUREMENT_INTERVAL > 60
if (MEASUREMENT_INTERVAL is None) or (MEASUREMENT_INTERVAL > 60):
    print("The application's 'MEASUREMENT_INTERVAL' cannot be empty or greater than 60")
    sys.exit(1)

# ============================================================================
#  Read Weather Underground Configuration Parameters
# ============================================================================
print("\nInitializing Weather Underground configuration")
wu_station_id = Config.STATION_ID
wu_station_key = Config.STATION_KEY
if (wu_station_id is None) or (wu_station_key is None):
    print("Missing values from the Weather Underground configuration file\n")
    sys.exit(1)

# we made it this far, so it must have worked...
print("Successfully read Weather Underground configuration values")
print("Station ID:", wu_station_id)
# print("Station key:", wu_station_key)

# ============================================================================
# initialize the Sense HAT object
# ============================================================================
try:
    print("Initializing the Sense HAT client")
    sense = SenseHat()
    # sense.set_rotation(180)
    # then write some text to the Sense HAT's 'screen'
    sense.show_message("Init", text_colour=[255, 255, 0], back_colour=[0, 0, 255])
    # clear the screen
    sense.clear()
    # get the current temp to use when checking the previous measurement
    last_temp = round(c_to_f(get_temp()), 1)
    print("Current temperature reading:", last_temp)
except:
    print("Unable to initialize the Sense HAT library:", sys.exc_info()[0])
    sys.exit(1)

# ============================================================================
# initialize temperusb thermometer object
# ============================================================================
try:
    temper_handler = temper.TemperHandler()
    temper_device = temper_handler.get_devices()[0]
    print("Current temper temperature:", c_to_f(get_temper_temp()) )
except:
    print("Unable to initialize the temperUSB thermometer")
    sys.exit(1)

# ============================================================================
# create data log file
# ============================================================================
try:
    # using this fixed file name for now...
    log_name = 'data.log'
    # if temp.log doesn't exist, make it
    if not os.path.isfile(log_name):
        with open(log_name, mode='w', encoding='utf-8') as f:
            json.dump([], f)

except:
    print("Couldn't initialize a log file!")

print("Initialization complete!")

# Now see what we're supposed to do next
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application\n")
        sys.exit(0)
