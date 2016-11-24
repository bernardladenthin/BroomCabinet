'''
Copyright 2016 Bernard Ladenthin bernard.ladenthin@gmail.com

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import RPi.GPIO as GPIO
import traceback
import logging
import time, threading
import sys
import urllib2
import os
import os.path
import subprocess

#apt-get rrdtool

def currentMillis():
    return int(round(time.time() * 1000))

lock = threading.Lock()
ledOnOffLock = threading.Lock()
inputChannel = 4;
outputChannel = 17;
inputCounter = 0;
lastSendTime = 0;
sendEveryNMilliSeconds = 60 * 1000;
readyToArchive = 0;
rrdTool='/usr/bin/rrdtool'
rrdToolPath=os.path.abspath(rrdTool)
rrdFilename='gpiocounter.rrd';
rrdDatabasePath=os.path.abspath(rrdFilename)

if not os.path.isfile(rrdDatabasePath):
    print "create rrd";
    subprocess.Popen([rrdToolPath,
        "create",
        rrdDatabasePath,
        '--start',
        'now',
        '--step',
        '60',
        'DS:gpiocounter:GAUGE:120:0:U', #120 seconds that may pass between two updates of this data source before the value of the data source is assumed to be UNKNOWN.
        'RRA:AVERAGE:0.5:1:60', #Archive point is saved every 1min, archive is kept for 1hour back.
        'RRA:AVERAGE:0.5:5:51840', #Archive point is saved every 5min, archive is kept for 6month back.
        'RRA:AVERAGE:0.5:60:43800' #Archive point is saved every 1hour, archive is kept for 5year back.
    ])

GPIO.setmode(GPIO.BCM)
GPIO.setup(inputChannel, GPIO.IN)
GPIO.setup(outputChannel, GPIO.OUT)

#def inputCallbackRising(channel):
#    print "inputCallbackRising"
#    GPIO.output(outputChannel, GPIO.LOW);

def ledOn():
    global outputChannel;
    GPIO.output(outputChannel, GPIO.HIGH);

def ledOff():
    global outputChannel;
    GPIO.output(outputChannel, GPIO.LOW);

def ledOnOff():
    with ledOnOffLock:
        ledOn();
        time.sleep(0.0005);
        ledOff();

def inputCallbackFalling(channel):
    global inputCounter, inputChannel, outputChannel;
    #print "inputCallbackFalling"
    t1 = threading.Thread(target = ledOnOff, args=());
    t1.start();
    with lock:
        inputCounter = inputCounter + 1;
    #print "inputCounter: " + str(inputCounter)

# (10000 impulses / kWh)
# (10000 impulses / kwh) * 16 kw = 160000 impulses
# 160000 impulses / 60 minutes = 2666.6 impulses / minute
# 2666.6 / 60 = 44 impulses / second => 44/s => (44 Hz)
# 1/44/s = 0.0227s^-1 = 227ms^-1 => 227ms for each pulse period
GPIO.add_event_detect(inputChannel, GPIO.FALLING, callback=inputCallbackFalling, bouncetime=1) # GPIO.RISING, GPIO.FALLING, GPIO.BOTH

try:
    print "Main loop is now running ..."
    print "Python version: " + sys.version
    mainLoopRun = True;
    while mainLoopRun:
        try:
            time.sleep(1)
            currentTimeInMillis = currentMillis();
            #print "main loop @" + str(currentTimeInMillis)

            if (currentTimeInMillis - lastSendTime > sendEveryNMilliSeconds):
                lastSendTime = currentTimeInMillis
                with lock:
                    readyToArchive = readyToArchive + inputCounter;
                    inputCounter = 0;
                # hint: enable to upload the value to a custom server
                #url = "http://example.com/savevalue.php?value=" + str(readyToArchive);
                #print "Try to open: " + url; 
                #urllib2.urlopen(url).read()
                subprocess.Popen([rrdToolPath, "update", rrdDatabasePath, "N:" + str(readyToArchive)]);
                readyToArchive = 0;
        except KeyboardInterrupt:
            print "KeyboardInterrupt"
            mainLoopRun = False;
        except:
            print "Unexpected error: ", sys.exc_info()[0]
    print "Main loop finished. Shut down."
finally:
    GPIO.cleanup()

print "Terminated"
