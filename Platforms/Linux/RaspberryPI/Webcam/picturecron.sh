#!/bin/sh
# Capture one image from a USB webcam and store it under
# /home/pi/cam/<YYYYMMDD>/<HH>/<YYYYMMDDHHMMSS>.jpg
# Flat variant (no date folders):
#fswebcam -r 1280x720 --jpeg 100 -D 3 -S 13 /home/pi/cam/$(date +"%Y%m%d%H%M%S").jpg

path="/home/pi/cam"

dateComplete=$(date +"%Y%m%d%H%M%S")
YMD=$(date +"%Y%m%d")
HOUR=$(date +"%H")

fullPath="$path"/"$YMD"/"$HOUR"
mkdir -p "$fullPath"
echo "$fullPath"

imgFile="$fullPath"/"$dateComplete".jpg
echo "$imgFile"

fswebcam -r 1280x720 --jpeg 100 -D 3 -S 13 "$imgFile"
