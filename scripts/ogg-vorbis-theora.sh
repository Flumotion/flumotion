#!/bin/bash
export FLUPATH=`pwd`/../flumotion

echo Starting controller
python $FLUPATH/controller.py  > /tmp/flumotion.controller.log 2>&1 &
sleep 3
xterm -T controller -e sh -c "tail -n 10000 -f /tmp/flumotion.controller.log" &

echo Starting video producer
python $FLUPATH/producer.py -v -c localhost -n producer-video -p "v4lsrc device=/dev/video0 ! video/x-raw-yuv,width=320,height=240,framerate=4.6875"  > /tmp/flumotion.producer-video.log 2>&1 &
sleep 3
xterm -T producer-video -e sh -c "tail -n 10000 -f /tmp/flumotion.producer-video.log" &

echo Starting audio producer
python $FLUPATH/producer.py -v -c localhost -n producer-audio -p "filesrc location=/home/audio/albums/Elbow\ -\ Asleep\ In\ The\ Back/Elbow\ -\ Newborn.ogg ! oggdemux ! vorbisdec"  > /tmp/flumotion.producer-audio.log 2>&1 &
sleep 20
xterm -T producer-audio -e sh -c "tail -f /tmp/flumotion.producer-audio.log" &

echo Starting converter
python $FLUPATH/converter.py -v -c localhost -s producer-audio,producer-video -n converter -p "{ @producer-audio ! rawvorbisenc name=aenc } { @producer-video ! theoraenc name=venc } aenc. ! queue max-size-buffers=4 ! oggmux name=mux venc. ! queue max-size-buffers=4 ! mux. mux."  > /tmp/flumotion.converter.log 2>&1 &
sleep 3
xterm -T converter -e sh -c "tail -f /tmp/flumotion.converter.log" &
                                                                                
echo Starting streamer
python $FLUPATH/streamer.py -v -c localhost -s converter -n streamer -p http -o 8080  > /tmp/flumotion.streamer.log 2>&1 &
sleep 3
xterm -T streamer -e sh -c "tail -n 10000 -f /tmp/flumotion.streamer.log" &

echo done
