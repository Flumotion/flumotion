#!/bin/bash
export FLUPATH=`pwd`/../flumotion

echo Starting controller
python $FLUPATH/controller.py  > /tmp/flumotion.controller.log 2>&1 &
sleep 3
xterm -T controller -e sh -c "tail -f /tmp/flumotion.controller.log" &

echo Starting producer for video
python $FLUPATH/producer.py -v -c localhost -n producer-video -p "v4lsrc device=/dev/video0 ! video/x-raw-yuv,width=320,height=240"  > /tmp/flumotion.producer-video.log 2>&1 &
sleep 3
xterm -T producer-video -e sh -c "tail -f /tmp/flumotion.producer-video.log" &

echo Starting producer for audio
python $FLUPATH/producer.py -v -c localhost -n producer-audio -p "alsasrc period-size=500 period-count=10 device=hw:1 ! audio/x-raw-int,rate=8000,signed=(boolean)true,endianness=1234,channels=1,width=16,depth=16"  > /tmp/flumotion.producer-audio.log 2>&1 &
sleep 3
xterm -T producer-audio -e sh -c "tail -f /tmp/flumotion.producer-audio.log" &

echo Starting converter
python $FLUPATH/converter.py -v -c localhost -s producer-audio,producer-video -n converter -p "{ @producer-audio ! mulawenc name=aenc } { @producer-video ! jpegenc quality=30 name=venc } aenc. ! queue max-size-buffers=4 ! multipartmux name=mux venc. ! queue max-size-buffers=4 ! mux. mux."  > /tmp/flumotion.converter.log 2>&1 &
sleep 3
xterm -T converter -e sh -c "tail -f /tmp/flumotion.converter.log" &

echo Starting streamer
python $FLUPATH/streamer.py -v -c localhost -s converter -n streamer -p http -o 8080  > /tmp/flumotion.streamer.log 2>&1 &
sleep 3
xterm -T streamer -e sh -c "tail -f /tmp/flumotion.streamer.log" &

echo done
