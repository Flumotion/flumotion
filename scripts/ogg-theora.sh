#!/bin/bash
export FLUPATH=`pwd`/../flumotion

echo Starting controller
python $FLUPATH/controller.py  > /tmp/flumotion.controller.log 2>&1 &
sleep 3
xterm -T controller -e sh -c "tail -n 10000 -f /tmp/flumotion.controller.log" &

echo Starting producer
python $FLUPATH/producer.py -v -c localhost -n producer -p "v4lsrc device=/dev/video0 ! video/x-raw-yuv,width=320,height=240,framerate=4.6875"  > /tmp/flumotion.producer.log 2>&1 &
sleep 10
xterm -T producer -e sh -c "tail -n 10000 -f /tmp/flumotion.producer.log" &

echo Starting converter
python $FLUPATH/converter.py -v -c localhost -s producer -n converter -p "ffmpegcolorspace ! theoraenc ! oggmux"  > /tmp/flumotion.converter.log 2>&1 &
sleep 3
xterm -T converter -e sh -c "tail -n 10000 -f /tmp/flumotion.converter.log" &

echo Starting streamer
python $FLUPATH/streamer.py -v -c localhost -s converter -n streamer -p http -o 8080  > /tmp/flumotion.streamer.log 2>&1 &
sleep 3
xterm -T streamer -e sh -c "tail -n 10000 -f /tmp/flumotion.streamer.log" &

echo done
